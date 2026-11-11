"""The functions behind each task (read from one table, write to the next).

They take normal db connections, so the DAG passes in the hook connections
but I can also call them from a script or test.
The data itself goes from table to table. I only return small summaries
(row counts etc.), those end up in XCom.
"""
from __future__ import annotations

import json
import logging

import pandas as pd

from . import config, db, kpis, transformation, validation
from .schema import ENRICHED_COLUMNS, KPI_TABLES, MYSQL_DDL, PG_SCHEMA, POSTGRES_DDL

log = logging.getLogger(__name__)

SOURCE_COLS = list(config.SOURCE_SCHEMA)


# --- create tables ---
def create_mysql_tables(mysql_conn) -> None:
    db.execute_script(mysql_conn, MYSQL_DDL)


def create_postgres_tables(pg_conn) -> None:
    db.execute_script(pg_conn, POSTGRES_DDL)


# --- validate ---
def _latest_audit(mysql_conn, batch_id: str) -> dict:
    audit = db.fetch_df(
        mysql_conn,
        "SELECT source_columns, type_coercion_failures, rows_in_file FROM ingestion_audit "
        "WHERE batch_id = %s ORDER BY id DESC LIMIT 1", (batch_id,))
    if audit.empty:
        raise validation.DataQualityError(f"No ingestion audit found for batch {batch_id}")
    row = audit.iloc[0]
    return {"source_columns": json.loads(row["source_columns"]),
            "type_coercion_failures": json.loads(row["type_coercion_failures"] or "{}"),
            "rows_in_file": int(row["rows_in_file"])}


def validate_stage(mysql_conn, batch_id: str, max_reject_ratio: float = config.MAX_REJECT_RATIO) -> dict:
    audit = _latest_audit(mysql_conn, batch_id)
    schema_check = validation.check_required_columns(audit["source_columns"])

    raw = db.fetch_df(mysql_conn, f"SELECT source_row_num, {', '.join(SOURCE_COLS)} "
                                  f"FROM stg_flight_prices_raw WHERE batch_id = %s", (batch_id,))
    if len(raw) != audit["rows_in_file"]:
        raise validation.DataQualityError(
            f"Staging has {len(raw)} rows but file had {audit['rows_in_file']}")

    result = validation.validate_rows(raw, audit["type_coercion_failures"])

    out = result.validated[["source_row_num", *SOURCE_COLS, "dq_status", "dq_flags"]].copy()
    out["batch_id"] = batch_id
    issues = result.issues.copy()
    issues.insert(0, "batch_id", batch_id)

    cur = mysql_conn.cursor()
    try:
        cur.execute("DELETE FROM stg_flight_prices_validated")
        cur.execute("DELETE FROM dq_issues WHERE batch_id = %s", (batch_id,))
        db.insert_df(mysql_conn, "stg_flight_prices_validated", out, config.INSERT_CHUNK_SIZE, commit=False)
        db.insert_df(mysql_conn, "dq_issues", issues, config.INSERT_CHUNK_SIZE, commit=False)
        mysql_conn.commit()
    except Exception:
        mysql_conn.rollback()
        raise
    finally:
        cur.close()

    summary = {**result.summary, **schema_check,
               "type_coercion_failures": audit["type_coercion_failures"]}
    summary["max_reject_ratio"] = max_reject_ratio
    validation.enforce_quality_gate(summary, max_reject_ratio)
    return summary


# --- transform + KPIs ---
def transform_stage(mysql_conn, batch_id: str) -> dict:
    validated = db.fetch_df(
        mysql_conn,
        f"SELECT source_row_num, {', '.join(SOURCE_COLS)}, dq_status FROM stg_flight_prices_validated "
        f"WHERE batch_id = %s AND dq_status = 'valid'", (batch_id,))
    enriched = transformation.transform(validated, batch_id)

    cur = mysql_conn.cursor()
    try:
        cur.execute("DELETE FROM stg_flight_prices_enriched")
        db.insert_df(mysql_conn, "stg_flight_prices_enriched", enriched, config.INSERT_CHUNK_SIZE, commit=False)
        mysql_conn.commit()
    except Exception:
        mysql_conn.rollback()
        raise
    finally:
        cur.close()
    return {
        "rows_enriched": len(enriched),
        "totals_recalculated": int(enriched["total_fare_recalculated"].sum()),
        "seasons": enriched["season"].value_counts().to_dict(),
        "season_source": enriched["season_source"].value_counts().to_dict(),
    }


def load_enriched(mysql_conn, batch_id: str) -> pd.DataFrame:
    df = db.fetch_df(mysql_conn, f"SELECT {', '.join(ENRICHED_COLUMNS)} FROM stg_flight_prices_enriched "
                                 f"WHERE batch_id = %s", (batch_id,))
    if df.empty:
        raise validation.DataQualityError("Enriched table is empty — nothing to compute KPIs on")
    return df


def kpi_stage(mysql_conn, batch_id: str, kpi_name: str, top_routes_limit: int = config.TOP_ROUTES_LIMIT) -> dict:
    enriched = load_enriched(mysql_conn, batch_id)
    fn = kpis.KPI_FUNCTIONS[kpi_name]
    if kpi_name == "kpi_popular_routes":
        result = fn(enriched, batch_id, top_n=top_routes_limit)
    else:
        result = fn(enriched, batch_id)
    result = result[list(KPI_TABLES[kpi_name])]

    cur = mysql_conn.cursor()
    try:
        cur.execute(f"DELETE FROM {kpi_name}")
        db.insert_df(mysql_conn, kpi_name, result, commit=False)
        mysql_conn.commit()
    except Exception:
        mysql_conn.rollback()
        raise
    finally:
        cur.close()
    preview = result.drop(columns=["batch_id"]).head(5)
    return {"kpi": kpi_name, "rows": len(result),
            "preview": json.loads(preview.to_json(orient="records", default_handler=str))}


# --- load to postgres ---
def load_to_postgres(mysql_conn, pg_conn, batch_id: str, run_summary: dict | None = None) -> dict:
    """Replace all the analytics tables in Postgres in one transaction.

    I read everything from MySQL first, so the Postgres tables are only locked
    for the short write part. Then TRUNCATE + COPY for every table and the run
    log, and one commit at the end. If anything fails it all rolls back, so
    whoever reads the tables sees either the old data or the new data, never
    half of it. COPY is used because it's a lot faster than inserts.
    """
    frames = {"fact_flight_prices": db.fetch_df(
        mysql_conn, f"SELECT {', '.join(ENRICHED_COLUMNS)} FROM stg_flight_prices_enriched WHERE batch_id = %s",
        (batch_id,))}
    for name, spec in KPI_TABLES.items():
        frames[name] = db.fetch_df(mysql_conn, f"SELECT {', '.join(spec)} FROM {name} WHERE batch_id = %s",
                                   (batch_id,))
    if frames["fact_flight_prices"].empty:
        raise validation.DataQualityError("No enriched rows to load into PostgreSQL")

    run_summary = run_summary or {}
    loaded: dict[str, int] = {}
    cur = pg_conn.cursor()
    try:
        cur.execute("SET LOCAL lock_timeout = '30s'")
        cur.execute("TRUNCATE " + ", ".join(f"{PG_SCHEMA}.{t}" for t in frames))
        for table, frame in frames.items():
            loaded[table] = db.pg_copy_df(cur, f"{PG_SCHEMA}.{table}", frame)
        cur.execute(
            f"""INSERT INTO {PG_SCHEMA}.pipeline_run_log
                    (batch_id, rows_in_file, rows_valid, rows_rejected, rows_loaded, dq_summary)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (batch_id) DO UPDATE SET
                    rows_in_file = EXCLUDED.rows_in_file, rows_valid = EXCLUDED.rows_valid,
                    rows_rejected = EXCLUDED.rows_rejected, rows_loaded = EXCLUDED.rows_loaded,
                    dq_summary = EXCLUDED.dq_summary, loaded_at = now()""",
            (batch_id, run_summary.get("rows_checked"), run_summary.get("rows_valid"),
             run_summary.get("rows_rejected"), loaded["fact_flight_prices"],
             json.dumps(run_summary.get("issues_by_rule", {}))),
        )
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        cur.close()
    log.info("Loaded into PostgreSQL: %s", loaded)
    return loaded


def verify_postgres_load(mysql_conn, pg_conn, batch_id: str) -> dict:
    """after the load, check that Postgres has exactly what MySQL had"""
    checks = {}
    pairs = {"fact_flight_prices": "stg_flight_prices_enriched", **{k: k for k in KPI_TABLES}}
    for pg_table, my_table in pairs.items():
        my_n = int(db.fetch_scalar(mysql_conn, f"SELECT COUNT(*) FROM {my_table} WHERE batch_id = %s", (batch_id,)))
        pg_n = int(db.fetch_scalar(pg_conn, f"SELECT COUNT(*) FROM {PG_SCHEMA}.{pg_table} WHERE batch_id = %s", (batch_id,)))
        checks[pg_table] = {"mysql": my_n, "postgres": pg_n}
        if my_n != pg_n:
            raise RuntimeError(f"Row count mismatch for {pg_table}: mysql={my_n} postgres={pg_n}")

    # a few sanity checks on the numbers too
    fact_n = checks["fact_flight_prices"]["postgres"]
    booking_sum = int(db.fetch_scalar(pg_conn, f"SELECT COALESCE(SUM(booking_count),0) FROM {PG_SCHEMA}.kpi_booking_count_by_airline"))
    route_sum = int(db.fetch_scalar(pg_conn, f"SELECT COALESCE(SUM(booking_count),0) FROM {PG_SCHEMA}.kpi_popular_routes"))
    my_total = float(db.fetch_scalar(mysql_conn, "SELECT COALESCE(SUM(total_fare),0) FROM stg_flight_prices_enriched WHERE batch_id = %s", (batch_id,)))
    pg_total = float(db.fetch_scalar(pg_conn, f"SELECT COALESCE(SUM(total_fare),0) FROM {PG_SCHEMA}.fact_flight_prices"))
    bad_totals = int(db.fetch_scalar(pg_conn, f"SELECT COUNT(*) FROM {PG_SCHEMA}.fact_flight_prices "
                                              f"WHERE abs(total_fare - (base_fare + tax_surcharge)) > {config.TOTAL_FARE_TOLERANCE}"))
    problems = []
    if booking_sum != fact_n:
        problems.append(f"airline booking counts sum {booking_sum} != fact rows {fact_n}")
    if route_sum != fact_n:
        problems.append(f"route booking counts sum {route_sum} != fact rows {fact_n}")
    if abs(my_total - pg_total) > 0.01:
        problems.append(f"sum(total_fare) differs: mysql={my_total} postgres={pg_total}")
    if bad_totals:
        problems.append(f"{bad_totals} fact rows violate total = base + tax")
    if problems:
        raise RuntimeError("Post-load reconciliation failed: " + "; ".join(problems))
    checks["sum_total_fare"] = round(pg_total, 2)
    log.info("Post-load verification passed: %s", checks)
    return checks
