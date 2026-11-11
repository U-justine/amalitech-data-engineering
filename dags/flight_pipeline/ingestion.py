"""Extract step: load the CSV into the MySQL raw table (stg_flight_prices_raw).

- header names get cleaned up first ("Base Fare (BDT)" -> base_fare), so a small
  change in the header doesn't break anything
- each column is converted to its type from config.SOURCE_SCHEMA. values that
  can't be converted become NULL, but I count them in ingestion_audit so the
  validation step can report them
- old rows are deleted and the new ones inserted in one transaction, so running
  it again doesn't create duplicates
- at the end I check that MySQL has the same number of rows as the file
"""
from __future__ import annotations

import json
import logging
import re

import pandas as pd

from . import config, db

log = logging.getLogger(__name__)

NA_VALUES = ["", "NA", "N/A", "n/a", "null", "NULL", "None", "NaN", "nan", "-"]


def normalize_column_name(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"\(\s*bdt\s*\)", "", s)          # remove "(BDT)"
    s = s.replace("&", " ")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return config.COLUMN_ALIASES.get(s, s)


def _varchar_len(sql_type: str) -> int | None:
    m = re.match(r"VARCHAR\((\d+)\)", sql_type)
    return int(m.group(1)) if m else None


def coerce_types(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """convert every column to its type. returns (typed df, how many values failed per column)"""
    out = pd.DataFrame(index=df.index)
    failures: dict[str, int] = {}
    for col, (sql_type, kind) in config.SOURCE_SCHEMA.items():
        if col not in df.columns:
            out[col] = None
            continue
        raw = df[col]
        present = raw.notna() & (raw.astype(str).str.strip() != "")
        if kind == "str":
            s = raw.astype(object).where(present, None)
            s = s.map(lambda v: re.sub(r"\s+", " ", str(v)).strip() if v is not None else None)
            limit = _varchar_len(sql_type)
            if limit:
                too_long = s.map(lambda v: v is not None and len(v) > limit)
                if too_long.any():
                    failures[f"{col}_truncated"] = int(too_long.sum())
                    s = s.map(lambda v: v[:limit] if v is not None else None)
            typed = s
            ok = present
        elif kind in ("float", "int"):
            cleaned = raw.astype(object).map(
                lambda v: str(v).replace(",", "").strip() if v is not None and not pd.isna(v) else None
            )
            typed = pd.to_numeric(cleaned, errors="coerce")
            if kind == "int":
                non_int = typed.notna() & (typed % 1 != 0)
                typed = typed.where(~non_int).round().astype("Int64")
            ok = typed.notna()
        elif kind == "datetime":
            typed = pd.to_datetime(raw.where(present, None), errors="coerce")
            ok = typed.notna()
        else:  # shouldn't happen unless I add a new type to the schema
            raise ValueError(f"Unknown kind {kind} for {col}")
        n_fail = int((present & ~ok).sum())
        if n_fail:
            failures[col] = n_fail
        out[col] = typed
    return out, failures


def read_source_csv(csv_path: str) -> tuple[pd.DataFrame, list[str], list[str]]:
    """read the csv as text (types come later). returns (df, original header, cleaned header)"""
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, na_values=NA_VALUES,
                     skipinitialspace=True, encoding="utf-8-sig")
    original = list(df.columns)
    canonical = [normalize_column_name(c) for c in original]
    df.columns = canonical
    df = df.loc[:, ~pd.Index(canonical).duplicated()]
    # skip completely empty lines, some exports have them at the end
    df = df.dropna(how="all").reset_index(drop=True)
    return df, original, canonical


def ingest_csv_to_mysql(conn, csv_path: str, batch_id: str) -> dict:
    raw, original_header, canonical_header = read_source_csv(csv_path)
    rows_in_file = len(raw)
    log.info("Read %s rows / %s columns from %s", rows_in_file, len(original_header), csv_path)

    typed, failures = coerce_types(raw)
    typed.insert(0, "source_row_num", range(1, rows_in_file + 1))
    typed["batch_id"] = batch_id

    expected = set(config.SOURCE_SCHEMA)
    missing = sorted(expected - set(canonical_header))
    unexpected = sorted(set(canonical_header) - expected)
    if unexpected:
        log.warning("Ignoring columns not in the source schema: %s", unexpected)

    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM stg_flight_prices_raw")      # not TRUNCATE, it auto-commits in MySQL
        db.insert_df(conn, "stg_flight_prices_raw", typed, config.INSERT_CHUNK_SIZE, commit=False)
        cur.execute(
            "INSERT INTO ingestion_audit (batch_id, source_file, source_columns, missing_columns, "
            "unexpected_columns, rows_in_file, rows_inserted, type_coercion_failures) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (batch_id, csv_path, json.dumps(canonical_header), json.dumps(missing),
             json.dumps(unexpected), rows_in_file, rows_in_file, json.dumps(failures)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

    loaded = db.fetch_scalar(conn, "SELECT COUNT(*) FROM stg_flight_prices_raw WHERE batch_id = %s", (batch_id,))
    if int(loaded) != rows_in_file:
        raise RuntimeError(f"Row count mismatch: file={rows_in_file}, mysql={loaded}")
    log.info("Ingestion verified: %s rows in MySQL match the file", loaded)

    return {
        "rows_in_file": rows_in_file,
        "rows_loaded": int(loaded),
        "source_columns": canonical_header,
        "missing_columns": missing,
        "unexpected_columns": unexpected,
        "type_coercion_failures": failures,
    }
