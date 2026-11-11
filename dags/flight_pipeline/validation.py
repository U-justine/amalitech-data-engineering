"""Validate step: check the raw rows before anything else uses them.

First the header: all required columns have to be there, otherwise the run
stops. (total_fare is the exception, I can calculate it, so only a warning.)

Then every row. If I can fix something safely I fix it, otherwise the row is
marked rejected. Every problem goes into the dq_issues table so I can see
exactly what happened to which row.

rule                      severity  what happens
missing_required_value    error     rejected
invalid_airport_code      error     rejected (after trim + uppercase)
airport_code_corrected    info      fixed, e.g. ' dac' -> 'DAC'
unknown_airport_code      warning   kept, just flagged
same_source_destination   error     rejected
missing_fare_imputed      warning   base or tax filled in from total - other
missing_fare              error     rejected (can't fill it in)
non_numeric_fare          error     value couldn't be read as a number
negative_fare             error     rejected
zero_base_fare            warning   kept, flagged
total_fare_missing        warning   calculated later in transform
total_fare_mismatch       warning   recalculated later in transform
arrival_before_departure  warning   kept, flagged
negative_days_before_dep  warning   set to NULL
duplicate_row             warning   kept, flagged (no booking id, could be real)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config

log = logging.getLogger(__name__)


class DataQualityError(Exception):
    """data is too bad to continue, the DAG turns this into a fail without retries"""


@dataclass
class ValidationResult:
    validated: pd.DataFrame
    issues: pd.DataFrame
    summary: dict = field(default_factory=dict)


def check_required_columns(source_columns: list[str]) -> dict:
    present = set(source_columns)
    missing = [c for c in config.REQUIRED_COLUMNS if c not in present]
    hard_missing = [c for c in missing if c not in config.DERIVABLE_COLUMNS]
    if hard_missing:
        raise DataQualityError(f"Required columns missing from source file: {hard_missing}")
    if missing:
        log.warning("Columns %s missing but derivable; they will be computed", missing)
    return {"missing_required": missing, "derivable_missing": [c for c in missing if c in config.DERIVABLE_COLUMNS]}


def _to_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(float)


def validate_rows(df: pd.DataFrame, coercion_failures: dict | None = None) -> ValidationResult:
    """check all rows. df needs source_row_num + the source columns"""
    df = df.copy().reset_index(drop=True)
    n = len(df)
    issues: list[dict] = []
    reject = np.zeros(n, dtype=bool)
    flags: list[list[str]] = [[] for _ in range(n)]

    def record(mask, rule, column, severity, action, values=None):
        idx = np.flatnonzero(np.asarray(mask, dtype=bool))
        for i in idx:
            val = None
            if values is not None:
                v = values.iloc[i]
                val = None if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v)[:255]
            issues.append({
                "source_row_num": int(df.at[i, "source_row_num"]),
                "rule_name": rule, "column_name": column, "original_value": val,
                "severity": severity, "action_taken": action,
            })
            flags[i].append(rule)
        return idx.size

    # clean up text first (trim, collapse double spaces)
    for col in ("airline", "source_name", "destination_name", "stopovers", "aircraft_type",
                "travel_class", "booking_source", "seasonality"):
        if col in df:
            df[col] = df[col].map(lambda v: " ".join(str(v).split()) if v is not None and not pd.isna(v) else None)
            df[col] = df[col].replace("", None)

    # 1. airline / source / destination must not be empty
    for col in config.CATEGORICAL_REQUIRED:
        orig = df[col].copy()
        blank = df[col].isna() | (df[col].astype(str).str.strip() == "")
        record(blank, "missing_required_value", col, "error", "rejected", orig)
        reject |= blank.to_numpy()

    # 2. airport codes have to be 3 capital letters
    for col in ("source", "destination"):
        orig = df[col].copy()
        cleaned = df[col].map(lambda v: str(v).strip().upper() if v is not None and not pd.isna(v) else None)
        changed = orig.notna() & (cleaned != orig)
        valid_fmt = cleaned.fillna("").str.match(config.IATA_PATTERN)
        record(changed & valid_fmt, "airport_code_corrected", col, "info", "corrected", orig)
        bad = orig.notna() & ~valid_fmt
        record(bad, "invalid_airport_code", col, "error", "rejected", orig)
        reject |= bad.to_numpy()
        unknown = valid_fmt & ~cleaned.isin(config.KNOWN_AIRPORTS)
        record(unknown, "unknown_airport_code", col, "warning", "flagged", orig)
        df[col] = cleaned

    same = df["source"].notna() & (df["source"] == df["destination"])
    record(same, "same_source_destination", "destination", "error", "rejected", df["destination"])
    reject |= same.to_numpy()

    # 3. fares
    failures = coercion_failures or {}
    for col in config.FARE_COLUMNS:
        df[col] = _to_numeric(df[col]) if col in df else np.nan
    base, tax, total = df["base_fare"], df["tax_surcharge"], df["total_fare"]

    # values that couldn't be parsed were already set to NULL in the extract step.
    # I only have the count per column from there, not the rows
    for col in config.FARE_COLUMNS:
        if failures.get(col):
            issues.append({"source_row_num": None, "rule_name": "non_numeric_fare", "column_name": col,
                           "original_value": f"{failures[col]} unparseable values", "severity": "error",
                           "action_taken": "nulled_at_ingestion"})

    can_impute_base = base.isna() & tax.notna() & total.notna()
    can_impute_tax = tax.isna() & base.notna() & total.notna()
    record(can_impute_base, "missing_fare_imputed", "base_fare", "warning", "imputed")
    record(can_impute_tax, "missing_fare_imputed", "tax_surcharge", "warning", "imputed")
    df.loc[can_impute_base, "base_fare"] = total[can_impute_base] - tax[can_impute_base]
    df.loc[can_impute_tax, "tax_surcharge"] = total[can_impute_tax] - base[can_impute_tax]
    base, tax = df["base_fare"], df["tax_surcharge"]

    for col in ("base_fare", "tax_surcharge"):
        missing = df[col].isna()
        record(missing, "missing_fare", col, "error", "rejected")
        reject |= missing.to_numpy()

    for col in config.FARE_COLUMNS:
        neg = df[col].notna() & (df[col] < 0)
        record(neg, "negative_fare", col, "error", "rejected", df[col])
        reject |= neg.to_numpy()

    record(base.notna() & (base == 0), "zero_base_fare", "base_fare", "warning", "flagged", base)
    record(total.isna() & base.notna() & tax.notna(), "total_fare_missing", "total_fare", "warning",
           "derive_in_transform")
    mismatch = total.notna() & base.notna() & tax.notna() & \
        ((total - (base + tax)).abs() > config.TOTAL_FARE_TOLERANCE)
    record(mismatch, "total_fare_mismatch", "total_fare", "warning", "recalculate_in_transform", total)

    # 4. other checks
    if {"departure_date_time", "arrival_date_time"} <= set(df.columns):
        dep = pd.to_datetime(df["departure_date_time"], errors="coerce")
        arr = pd.to_datetime(df["arrival_date_time"], errors="coerce")
        record(dep.notna() & arr.notna() & (arr < dep), "arrival_before_departure",
               "arrival_date_time", "warning", "flagged", df["arrival_date_time"])
    if "days_before_departure" in df:
        dbd = pd.to_numeric(df["days_before_departure"], errors="coerce")
        neg = dbd.notna() & (dbd < 0)
        record(neg, "negative_days_before_dep", "days_before_departure", "warning", "set_null", dbd)
        df["days_before_departure"] = dbd.where(~neg).astype("Int64")

    src_cols = [c for c in config.SOURCE_SCHEMA if c in df.columns]
    dup = df.duplicated(subset=src_cols, keep="first")
    record(dup, "duplicate_row", None, "warning", "flagged")

    # build the result
    df["dq_status"] = np.where(reject, "rejected", "valid")
    df["dq_flags"] = [";".join(dict.fromkeys(f))[:500] or None for f in flags]

    issues_df = pd.DataFrame(issues, columns=["source_row_num", "rule_name", "column_name",
                                              "original_value", "severity", "action_taken"])
    rejected = int(reject.sum())
    summary = {
        "rows_checked": n,
        "rows_valid": n - rejected,
        "rows_rejected": rejected,
        "reject_ratio": round(rejected / n, 6) if n else 0.0,
        "issues_by_rule": issues_df.groupby("rule_name").size().to_dict() if not issues_df.empty else {},
    }
    summary["issues_by_rule"] = {k: int(v) for k, v in summary["issues_by_rule"].items()}
    log.info("Validation summary: %s", summary)
    return ValidationResult(validated=df, issues=issues_df, summary=summary)


def enforce_quality_gate(summary: dict, max_reject_ratio: float = config.MAX_REJECT_RATIO) -> None:
    if summary["rows_checked"] == 0:
        raise DataQualityError("Source file contained no rows")
    if summary["rows_valid"] == 0:
        raise DataQualityError("No valid rows after validation")
    if summary["reject_ratio"] > max_reject_ratio:
        raise DataQualityError(
            f"Reject ratio {summary['reject_ratio']:.2%} exceeds threshold {max_reject_ratio:.2%}"
        )
