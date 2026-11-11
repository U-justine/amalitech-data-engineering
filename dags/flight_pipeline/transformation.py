"""Transform step: take the valid rows and add the columns I need for the KPIs.

- total_fare = base_fare + tax_surcharge when it's missing or doesn't add up
- season comes from the Seasonality column. only if that's empty do I work it
  out from the departure date
- is_peak_season = anything that isn't "Regular" (Eid, Hajj, Winter Holidays)
- plus date parts (year, month, weekday), the route (DAC-DXB) and a bucket for
  how many days before departure the ticket was booked
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import config
from .schema import ENRICHED_COLUMNS

log = logging.getLogger(__name__)


def normalize_season(value) -> str | None:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    key = re.sub(r"[^a-z ]+", " ", str(value).lower())
    key = " ".join(key.split())
    if not key:
        return None
    return config.SEASON_ALIASES.get(key, str(value).strip().title())


def derive_season(d) -> str:
    """guess the season from the departure date, only used when Seasonality is empty"""
    if d is None or pd.isna(d):
        return config.REGULAR_SEASON
    d = pd.Timestamp(d).date()
    for eid in config.EID_DATES:
        if eid - timedelta(days=config.EID_WINDOW_DAYS_BEFORE) <= d <= eid + timedelta(days=config.EID_WINDOW_DAYS_AFTER):
            return "Eid"
    (sm, sd), (em, ed) = config.WINTER_HOLIDAY_WINDOW
    if (d.month, d.day) >= (sm, sd) or (d.month, d.day) <= (em, ed):
        return "Winter Holidays"
    return config.REGULAR_SEASON


def lead_bucket(days) -> str | None:
    if days is None or pd.isna(days):
        return None
    days = int(days)
    if days <= 7:
        return "0-7 days"
    if days <= 14:
        return "8-14 days"
    if days <= 30:
        return "15-30 days"
    if days <= 60:
        return "31-60 days"
    return "61+ days"


def transform(validated: pd.DataFrame, batch_id: str) -> pd.DataFrame:
    df = validated[validated["dq_status"] == "valid"].copy()
    for col in config.FARE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

    # total fare = base + tax, but only where it's missing or wrong
    expected = (df["base_fare"] + df["tax_surcharge"]).round(2)
    recalc = df["total_fare"].isna() | ((df["total_fare"] - expected).abs() > config.TOTAL_FARE_TOLERANCE)
    df["total_fare"] = np.where(recalc, expected, df["total_fare"]).round(2)
    df["total_fare_recalculated"] = recalc.astype(bool)

    # date parts
    dep = pd.to_datetime(df["departure_date_time"], errors="coerce")
    df["departure_date_time"] = dep
    df["arrival_date_time"] = pd.to_datetime(df["arrival_date_time"], errors="coerce")
    df["departure_date"] = dep.dt.date
    df["departure_year"] = dep.dt.year.astype("Int64")
    df["departure_month"] = dep.dt.month.astype("Int64")
    df["departure_weekday"] = dep.dt.day_name()

    # season: from the file if it's there, otherwise from the date
    season_src = df["seasonality"].map(normalize_season) if "seasonality" in df else pd.Series(None, index=df.index)
    has_src = season_src.notna()
    derived = dep.map(derive_season)
    df["season"] = season_src.where(has_src, derived)
    df["season_source"] = np.where(has_src, "dataset", np.where(dep.notna(), "derived", "default"))
    df["is_peak_season"] = (df["season"] != config.REGULAR_SEASON).astype(bool)

    # route + how early it was booked
    df["route"] = df["source"] + "-" + df["destination"]
    df["days_before_departure"] = pd.to_numeric(df["days_before_departure"], errors="coerce").astype("Int64")
    df["booking_lead_bucket"] = df["days_before_departure"].map(lead_bucket)
    df["source_row_num"] = df["source_row_num"].astype(int)
    df["batch_id"] = batch_id

    out = df[list(ENRICHED_COLUMNS)].reset_index(drop=True)
    log.info("Transformed %s rows (%s totals recalculated, %s seasons derived)",
             len(out), int(recalc.sum()), int((~has_src).sum()))
    return out
