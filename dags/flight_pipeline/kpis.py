"""The 4 KPIs, one function each, plain pandas.

They all use the enriched table (so only valid rows). Each one returns a
DataFrame with the same columns as its table in schema.KPI_TABLES.
"""
from __future__ import annotations

import pandas as pd

from . import config


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ("total_fare", "base_fare", "tax_surcharge"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df["is_peak_season"] = df["is_peak_season"].astype(int).astype(bool)
    return df


def avg_fare_by_airline(df: pd.DataFrame, batch_id: str) -> pd.DataFrame:
    """average total fare per airline, plus median/min/max so the average makes more sense"""
    df = _prep(df)
    g = df.groupby("airline")
    out = pd.DataFrame({
        "booking_count": g.size(),
        "avg_total_fare": g["total_fare"].mean(),
        "median_total_fare": g["total_fare"].median(),
        "min_total_fare": g["total_fare"].min(),
        "max_total_fare": g["total_fare"].max(),
        "avg_base_fare": g["base_fare"].mean(),
        "avg_tax_surcharge": g["tax_surcharge"].mean(),
    }).reset_index()
    out = out.sort_values("avg_total_fare", ascending=False).reset_index(drop=True)
    out["fare_rank"] = range(1, len(out) + 1)
    out["batch_id"] = batch_id
    return out.round(2)


def seasonal_fare_variation(df: pd.DataFrame, batch_id: str) -> pd.DataFrame:
    """Seasonal fare variation.

    Two kinds of rows in the same table:
      season    - each season compared to the Regular season
      peak_flag - all peak seasons together vs non-peak
    pct_diff_vs_baseline = (avg - regular avg) / regular avg * 100
    """
    df = _prep(df)
    rows = []

    by_season = df.groupby(["season", "is_peak_season"])["total_fare"].agg(["size", "mean", "median"]).reset_index()
    regular = df.loc[~df["is_peak_season"], "total_fare"]
    regular_avg = regular.mean() if len(regular) else None
    for r in by_season.itertuples(index=False):
        rows.append({"grouping_level": "season", "season_label": r.season, "is_peak_season": bool(r.is_peak_season),
                     "booking_count": int(r.size), "avg_total_fare": r.mean, "median_total_fare": r.median,
                     "baseline_avg_fare": regular_avg})

    for flag, label in ((True, "Peak"), (False, "Non-Peak")):
        part = df.loc[df["is_peak_season"] == flag, "total_fare"]
        if len(part):
            rows.append({"grouping_level": "peak_flag", "season_label": label, "is_peak_season": flag,
                         "booking_count": int(len(part)), "avg_total_fare": part.mean(),
                         "median_total_fare": part.median(), "baseline_avg_fare": regular_avg})

    out = pd.DataFrame(rows)
    if regular_avg:
        out["pct_diff_vs_baseline"] = (out["avg_total_fare"] - regular_avg) / regular_avg * 100
    else:
        out["pct_diff_vs_baseline"] = None
    out["batch_id"] = batch_id
    out = out.sort_values(["grouping_level", "avg_total_fare"], ascending=[False, False]).reset_index(drop=True)
    return out.round(2)


def booking_count_by_airline(df: pd.DataFrame, batch_id: str) -> pd.DataFrame:
    """bookings per airline (1 row = 1 booking) and the % share"""
    counts = df.groupby("airline").size().sort_values(ascending=False)
    out = counts.rename("booking_count").reset_index()
    out["booking_share_pct"] = (out["booking_count"] / out["booking_count"].sum() * 100).round(2)
    out["booking_rank"] = out["booking_count"].rank(method="min", ascending=False).astype(int)
    out["batch_id"] = batch_id
    return out


def popular_routes(df: pd.DataFrame, batch_id: str, top_n: int = config.TOP_ROUTES_LIMIT) -> pd.DataFrame:
    """Routes ranked by number of bookings.

    I keep all routes with their rank and mark the top N with is_top_route.
    If two routes have the same count, the higher average fare goes first,
    then the name, so the ranking is the same every run.
    """
    df = _prep(df)
    names = df.groupby("route")[["source_name", "destination_name"]].first()
    g = df.groupby(["route", "source", "destination"])
    out = g.agg(booking_count=("total_fare", "size"), avg_total_fare=("total_fare", "mean")).reset_index()
    out = out.join(names, on="route")
    out = out.sort_values(["booking_count", "avg_total_fare", "route"], ascending=[False, False, True]).reset_index(drop=True)
    out["route_rank"] = range(1, len(out) + 1)
    out["is_top_route"] = out["route_rank"] <= top_n
    out["avg_total_fare"] = out["avg_total_fare"].round(2)
    out["batch_id"] = batch_id
    return out[["route_rank", "route", "source", "source_name", "destination", "destination_name",
                "booking_count", "avg_total_fare", "is_top_route", "batch_id"]]


KPI_FUNCTIONS = {
    "kpi_avg_fare_by_airline": avg_fare_by_airline,
    "kpi_seasonal_fare_variation": seasonal_fare_variation,
    "kpi_booking_count_by_airline": booking_count_by_airline,
    "kpi_popular_routes": popular_routes,
}
