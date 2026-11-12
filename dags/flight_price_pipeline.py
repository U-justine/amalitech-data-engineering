"""
### Flight Price Analysis - Bangladesh

ETL for the Kaggle "Flight Price Dataset of Bangladesh". The CSV goes into MySQL first
(staging), gets validated and cleaned, then I calculate the 4 KPIs and load everything
into PostgreSQL (schema `analytics`).
"""

from __future__ import annotations

import hashlib
import os
import sys
from contextlib import closing
from datetime import datetime, timedelta

from airflow.sdk import Param, TaskGroup, dag, get_current_context, task   # airflow 3 imports
from airflow.exceptions import AirflowFailException
from airflow.providers.mysql.hooks.mysql import MySqlHook
from airflow.providers.postgres.hooks.postgres import PostgresHook

# airflow 3 didn't find my flight_pipeline folder when I ran `airflow dags test`,
# so I add the dags folder to the path myself
_DAG_DIR = os.path.dirname(os.path.abspath(__file__))
if _DAG_DIR not in sys.path:
    sys.path.insert(0, _DAG_DIR)

from flight_pipeline import alerts, config, ingestion, report, stages, watermark  # noqa: E402
from flight_pipeline.kpis import KPI_FUNCTIONS  # noqa: E402
from flight_pipeline.validation import DataQualityError  # noqa: E402


# --- small helpers used by the tasks ---
def mysql_connection():
    """connection to the MySQL staging db (airflow connection mysql_staging)"""
    return closing(MySqlHook(mysql_conn_id=config.MYSQL_CONN_ID).get_conn())


def postgres_connection():
    """connection to the Postgres analytics db (airflow connection postgres_analytics)"""
    return closing(PostgresHook(postgres_conn_id=config.POSTGRES_CONN_ID).get_conn())


def batch_id() -> str:
    """I use the run_id as batch_id, so every row says which run loaded it"""
    return get_current_context()["run_id"]


def params() -> dict:
    """params of this run (defaults for the daily run, or what I typed when triggering)"""
    return get_current_context()["params"]


def file_fingerprint(path: str) -> dict:
    """check the csv exists and isn't empty, return size + md5"""
    if not os.path.isfile(path):
        # normal exception on purpose, so Airflow retries (the file might just be late)
        raise FileNotFoundError(f"Source file not found yet: {path}")
    size = os.path.getsize(path)
    if size == 0:
        raise ValueError(f"Source file is empty (still being written?): {path}")
    md5 = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            md5.update(chunk)
    return {"path": path, "bytes": size, "md5": md5.hexdigest()}


# --- params, default args, retries ---
DAG_ID = "flight_price_pipeline"

DAG_PARAMS = {
    "csv_path": Param(
        config.CSV_PATH, type="string",
        description="Path of the csv inside the container (the data/ folder is /opt/airflow/data).",
    ),
    "max_reject_ratio": Param(
        config.MAX_REJECT_RATIO, type="number", minimum=0, maximum=1,
        description="Stop the run if more than this part of the rows is bad (0.05 = 5%).",
    ),
    "top_routes_limit": Param(
        config.TOP_ROUTES_LIMIT, type="integer", minimum=1, maximum=100,
        description="How many routes count as top routes.",
    ),
    "send_success_email": Param(
        config.ALERT_EMAIL_ON_SUCCESS, type="boolean",
        description="Send me an email when the run works too (failures always send one).",
    ),
    "force_full_reload": Param(
        False, type="boolean",
        description="Load the file even if it's the same as last time (ignore the watermark).",
    ),
}

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    # retries: wait 1 min, then 2, then 4 (max 10)
    "retries": config.TASK_RETRIES,
    "retry_delay": timedelta(seconds=config.RETRY_DELAY_SECONDS),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(seconds=config.MAX_RETRY_DELAY_SECONDS),
    "execution_timeout": timedelta(seconds=config.DEFAULT_TASK_TIMEOUT_SECONDS),
    # alerts, see flight_pipeline/alerts.py
    "on_execute_callback": alerts.record_task_start,      # remember start time (for the slow check)
    "on_retry_callback": alerts.task_retry_alert,          # RETRYING -> alerts.log (+ email if on)
    "on_failure_callback": alerts.task_failure_alert,      # FAILED / TIMED OUT -> email + alerts.log
    "on_success_callback": alerts.task_duration_check,     # SLOW TASK -> email
}


@dag(
    dag_id=DAG_ID,
    description="Bangladesh flight prices ETL: CSV -> MySQL staging -> validate/transform/KPIs -> PostgreSQL",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,                     # don't run all the old days since start_date
    max_active_runs=1,                 # two runs at once would overwrite each other's tables
    max_active_tasks=8,
    dagrun_timeout=timedelta(seconds=config.DAGRUN_TIMEOUT_SECONDS),
    default_args=default_args,
    params=DAG_PARAMS,
    tags=["flights", "etl", "mysql", "postgres", "kpi"],
    doc_md=__doc__,
)
def flight_price_pipeline():

    # ---------- extract ----------
    @task(
        retries=config.SOURCE_FILE_RETRIES,
        retry_delay=timedelta(seconds=config.SOURCE_FILE_RETRY_DELAY_SECONDS),
        retry_exponential_backoff=False,
        doc_md="""Checks the csv is there and not empty. If not, it tries again every 5 min (3 times),
        in case the file is just late. If it still fails: put `Flight_Price_Dataset_of_Bangladesh.csv`
        in the `data/` folder and clear this task.""",
    )
    def check_source_file() -> dict:
        return file_fingerprint(params()["csv_path"])

    @task.short_circuit(doc_md="""Watermark check. Compares the md5 of the csv with the one saved
        after the last good load. Same file -> returns False and everything after this is skipped
        (the run still ends green). Different file, first run, or `force_full_reload` -> carries on.""")
    def check_watermark(file_info: dict) -> bool:
        with postgres_connection() as pg:
            stored = watermark.get(pg, DAG_ID)
        run, reason = watermark.should_run(file_info["md5"], stored, bool(params()["force_full_reload"]))
        print(f"Watermark: {reason}")
        return run

    @task(doc_md="Creates the MySQL staging tables if they don't exist yet. Safe to run again.")
    def create_staging_tables() -> None:
        with mysql_connection() as conn:
            stages.create_mysql_tables(conn)

    @task(doc_md="""Reads the csv, cleans the header names, converts the types and loads it into
        `stg_flight_prices_raw` (old rows deleted, new ones inserted, one transaction). Fails if
        MySQL doesn't end up with the same number of rows as the file.""")
    def extract_csv_to_mysql(file_info: dict) -> dict:
        with mysql_connection() as conn:
            return ingestion.ingest_csv_to_mysql(conn, file_info["path"], batch_id())

    # ---------- transform ----------
    @task(doc_md="""Data quality checks (required columns, empty values, types, negative fares,
        airport codes, totals). Every problem goes to `dq_issues` in MySQL. If a required column is
        missing or too many rows are bad, the run stops straight away, no retries.
        To see what went wrong: `SELECT rule_name, COUNT(*) FROM dq_issues GROUP BY 1;`""")
    def validate_data(extract_summary: dict) -> dict:
        try:
            with mysql_connection() as conn:
                return stages.validate_stage(conn, batch_id(), float(params()["max_reject_ratio"]))
        except DataQualityError as exc:          # bad data -> fail now, retrying won't help
            raise AirflowFailException(str(exc)) from exc

    @task(doc_md="""Only the valid rows. Fixes total fare (base + tax) where needed and adds season,
        peak flag, route and date columns -> `stg_flight_prices_enriched`.""")
    def transform_data(validation_summary: dict) -> dict:
        with mysql_connection() as conn:
            return stages.transform_stage(conn, batch_id())

    @task(doc_md="Calculates one KPI from `stg_flight_prices_enriched` and saves it in its `kpi_*` table.")
    def compute_kpi(kpi_name: str) -> dict:
        with mysql_connection() as conn:
            return stages.kpi_stage(conn, batch_id(), kpi_name, int(params()["top_routes_limit"]))

    # ---------- load ----------
    @task(doc_md="Creates the Postgres tables, indexes and views if they don't exist yet. Safe to run again.")
    def create_analytics_tables() -> None:
        with postgres_connection() as conn:
            stages.create_postgres_tables(conn)

    @task(
        execution_timeout=timedelta(seconds=config.LOAD_TIMEOUT_SECONDS),
        retry_delay=timedelta(seconds=config.RETRY_DELAY_SECONDS * 2),
        doc_md="""Replaces the fact table and the KPI tables in Postgres in one transaction
        (TRUNCATE + COPY). If it fails or times out everything rolls back, so the old data stays.
        Retries wait 2, 4, 8 min.""",
    )
    def load_to_postgres(validation_summary: dict, kpi_results: list) -> dict:
        with mysql_connection() as my, postgres_connection() as pg:
            return stages.load_to_postgres(my, pg, batch_id(), validation_summary)

    @task(doc_md="""Checks the load: same row counts in both databases, bookings add up to the
        number of rows, same total fare sum, and total = base + tax everywhere.""")
    def verify_postgres_load(load_result: dict) -> dict:
        with mysql_connection() as my, postgres_connection() as pg:
            return stages.verify_postgres_load(my, pg, batch_id())

    @task(doc_md="Saves the md5 of the file that was just loaded, so the next run can skip it if nothing changed.")
    def update_watermark(file_info: dict, load_result: dict, checks: dict) -> dict:
        # only reached when the load and the checks passed, so the file really is done
        with postgres_connection() as pg:
            return watermark.save(pg, DAG_ID, file_info, int(load_result["fact_flight_prices"]), batch_id())

    @task(doc_md="""Makes `data/reports/kpi_report.html` from the KPI tables in Postgres: the main
        numbers and a chart for each KPI. Just open it in the browser.""")
    def build_kpi_report(checks: dict) -> dict:
        with postgres_connection() as pg:
            return report.write_report(pg, config.REPORT_DIR)

    @task(
        retries=config.NOTIFY_RETRIES,
        on_success_callback=alerts.on_success,           # last task, so it also checks the whole run time
        doc_md="Logs a summary of the run and emails it if `send_success_email` is on.",
    )
    def notify_success(validation_summary: dict, load_result: dict, checks: dict, report_info: dict,
                       wm_info: dict) -> dict:
        summary = {
            "rows_in_file": validation_summary.get("rows_checked"),
            "rows_valid": validation_summary.get("rows_valid"),
            "rows_rejected": validation_summary.get("rows_rejected"),
            "reject_ratio": validation_summary.get("reject_ratio"),
            "rows_loaded": load_result.get("fact_flight_prices"),
            "sum_total_fare_bdt": checks.get("sum_total_fare"),
            "kpi_report": "data/reports/" + os.path.basename(report_info.get("path", "kpi_report.html")),
            "watermark_md5": wm_info.get("file_md5"),
        }
        if params()["send_success_email"]:
            alerts.run_summary_email(summary, batch_id())
        print(f"Run summary: {summary}")
        return summary

    # ---------- order of the tasks ----------
    # extract:   check_source_file >> check_watermark >> create_staging_tables >> extract_csv_to_mysql
    # transform: validate_data >> transform_data >> 4 KPI tasks (parallel)
    # load:      create_analytics_tables >> load_to_postgres >> verify_postgres_load >> update_watermark
    #            >> build_kpi_report >> notify_success
    # if check_watermark says "same file", everything after it is skipped
    # and then extract >> transform >> load
    with TaskGroup("extract", tooltip="CSV -> MySQL staging") as extract:
        file_info = check_source_file()
        wm_check = check_watermark(file_info)
        staging_ddl = create_staging_tables()
        extracted = extract_csv_to_mysql(file_info)
        file_info >> wm_check >> staging_ddl >> extracted

    with TaskGroup("transform", tooltip="Validate, enrich and compute KPIs in MySQL") as transform:
        validated = validate_data(extracted)
        transformed = transform_data(validated)
        with TaskGroup("kpis", tooltip="4 KPIs computed in parallel") as kpis:
            kpi_results = [compute_kpi.override(task_id=name)(name) for name in KPI_FUNCTIONS]
        transformed >> kpis

    with TaskGroup("load", tooltip="MySQL -> PostgreSQL analytics, verify, notify") as load:
        analytics_ddl = create_analytics_tables()
        loaded = load_to_postgres(validated, kpi_results)
        checks = verify_postgres_load(loaded)
        wm_info = update_watermark(file_info, loaded, checks)
        report_info = build_kpi_report(checks)
        done = notify_success(validated, loaded, checks, report_info, wm_info)
        analytics_ddl >> loaded >> checks >> wm_info >> report_info >> done

    extract >> transform >> load


flight_price_pipeline()
