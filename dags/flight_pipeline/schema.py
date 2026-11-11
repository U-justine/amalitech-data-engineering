"""CREATE TABLE statements for MySQL (staging) and PostgreSQL (analytics).

The raw and validated tables are built from config.SOURCE_SCHEMA, so if I add
a column there it shows up here too.
"""
from __future__ import annotations

from .config import SOURCE_SCHEMA

_SOURCE_COLS_MYSQL = ",\n    ".join(f"{c} {t} NULL" for c, (t, _) in SOURCE_SCHEMA.items())

# columns of the enriched / fact table: name -> (mysql type, postgres type)
ENRICHED_COLUMNS: dict[str, tuple[str, str]] = {
    "source_row_num": ("INT NOT NULL", "INTEGER NOT NULL"),
    "airline": ("VARCHAR(100) NOT NULL", "VARCHAR(100) NOT NULL"),
    "source": ("VARCHAR(10) NOT NULL", "VARCHAR(10) NOT NULL"),
    "source_name": ("VARCHAR(150)", "VARCHAR(150)"),
    "destination": ("VARCHAR(10) NOT NULL", "VARCHAR(10) NOT NULL"),
    "destination_name": ("VARCHAR(150)", "VARCHAR(150)"),
    "route": ("VARCHAR(25) NOT NULL", "VARCHAR(25) NOT NULL"),
    "departure_date_time": ("DATETIME", "TIMESTAMP"),
    "arrival_date_time": ("DATETIME", "TIMESTAMP"),
    "departure_date": ("DATE", "DATE"),
    "departure_year": ("SMALLINT", "SMALLINT"),
    "departure_month": ("SMALLINT", "SMALLINT"),
    "departure_weekday": ("VARCHAR(10)", "VARCHAR(10)"),
    "duration_hrs": ("DECIMAL(8,4)", "NUMERIC(8,4)"),
    "stopovers": ("VARCHAR(30)", "VARCHAR(30)"),
    "aircraft_type": ("VARCHAR(60)", "VARCHAR(60)"),
    "travel_class": ("VARCHAR(30)", "VARCHAR(30)"),
    "booking_source": ("VARCHAR(60)", "VARCHAR(60)"),
    "base_fare": ("DECIMAL(14,2) NOT NULL", "NUMERIC(14,2) NOT NULL"),
    "tax_surcharge": ("DECIMAL(14,2) NOT NULL", "NUMERIC(14,2) NOT NULL"),
    "total_fare": ("DECIMAL(14,2) NOT NULL", "NUMERIC(14,2) NOT NULL"),
    "total_fare_recalculated": ("BOOLEAN NOT NULL", "BOOLEAN NOT NULL"),
    "season": ("VARCHAR(40) NOT NULL", "VARCHAR(40) NOT NULL"),
    "season_source": ("VARCHAR(10) NOT NULL", "VARCHAR(10) NOT NULL"),
    "is_peak_season": ("BOOLEAN NOT NULL", "BOOLEAN NOT NULL"),
    "days_before_departure": ("INT", "INTEGER"),
    "booking_lead_bucket": ("VARCHAR(20)", "VARCHAR(20)"),
    "batch_id": ("VARCHAR(250) NOT NULL", "VARCHAR(250) NOT NULL"),
}

KPI_TABLES: dict[str, dict[str, tuple[str, str]]] = {
    "kpi_avg_fare_by_airline": {
        "airline": ("VARCHAR(100) NOT NULL", "VARCHAR(100) NOT NULL"),
        "booking_count": ("INT NOT NULL", "INTEGER NOT NULL"),
        "avg_total_fare": ("DECIMAL(14,2)", "NUMERIC(14,2)"),
        "median_total_fare": ("DECIMAL(14,2)", "NUMERIC(14,2)"),
        "min_total_fare": ("DECIMAL(14,2)", "NUMERIC(14,2)"),
        "max_total_fare": ("DECIMAL(14,2)", "NUMERIC(14,2)"),
        "avg_base_fare": ("DECIMAL(14,2)", "NUMERIC(14,2)"),
        "avg_tax_surcharge": ("DECIMAL(14,2)", "NUMERIC(14,2)"),
        "fare_rank": ("INT", "INTEGER"),
        "batch_id": ("VARCHAR(250) NOT NULL", "VARCHAR(250) NOT NULL"),
    },
    "kpi_seasonal_fare_variation": {
        "grouping_level": ("VARCHAR(20) NOT NULL", "VARCHAR(20) NOT NULL"),
        "season_label": ("VARCHAR(40) NOT NULL", "VARCHAR(40) NOT NULL"),
        "is_peak_season": ("BOOLEAN NOT NULL", "BOOLEAN NOT NULL"),
        "booking_count": ("INT NOT NULL", "INTEGER NOT NULL"),
        "avg_total_fare": ("DECIMAL(14,2)", "NUMERIC(14,2)"),
        "median_total_fare": ("DECIMAL(14,2)", "NUMERIC(14,2)"),
        "baseline_avg_fare": ("DECIMAL(14,2)", "NUMERIC(14,2)"),
        "pct_diff_vs_baseline": ("DECIMAL(8,2)", "NUMERIC(8,2)"),
        "batch_id": ("VARCHAR(250) NOT NULL", "VARCHAR(250) NOT NULL"),
    },
    "kpi_booking_count_by_airline": {
        "airline": ("VARCHAR(100) NOT NULL", "VARCHAR(100) NOT NULL"),
        "booking_count": ("INT NOT NULL", "INTEGER NOT NULL"),
        "booking_share_pct": ("DECIMAL(6,2)", "NUMERIC(6,2)"),
        "booking_rank": ("INT", "INTEGER"),
        "batch_id": ("VARCHAR(250) NOT NULL", "VARCHAR(250) NOT NULL"),
    },
    "kpi_popular_routes": {
        "route_rank": ("INT NOT NULL", "INTEGER NOT NULL"),
        "route": ("VARCHAR(25) NOT NULL", "VARCHAR(25) NOT NULL"),
        "source": ("VARCHAR(10) NOT NULL", "VARCHAR(10) NOT NULL"),
        "source_name": ("VARCHAR(150)", "VARCHAR(150)"),
        "destination": ("VARCHAR(10) NOT NULL", "VARCHAR(10) NOT NULL"),
        "destination_name": ("VARCHAR(150)", "VARCHAR(150)"),
        "booking_count": ("INT NOT NULL", "INTEGER NOT NULL"),
        "avg_total_fare": ("DECIMAL(14,2)", "NUMERIC(14,2)"),
        "is_top_route": ("BOOLEAN NOT NULL", "BOOLEAN NOT NULL"),
        "batch_id": ("VARCHAR(250) NOT NULL", "VARCHAR(250) NOT NULL"),
    },
}


def _cols(spec: dict[str, tuple[str, str]], idx: int) -> str:
    return ",\n    ".join(f"{c} {types[idx]}" for c, types in spec.items())


MYSQL_DDL = f"""
CREATE TABLE IF NOT EXISTS stg_flight_prices_raw (
    source_row_num INT NOT NULL PRIMARY KEY,
    {_SOURCE_COLS_MYSQL},
    batch_id VARCHAR(250) NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingestion_audit (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id VARCHAR(250) NOT NULL,
    source_file VARCHAR(500) NOT NULL,
    source_columns TEXT NOT NULL,
    missing_columns TEXT,
    unexpected_columns TEXT,
    rows_in_file INT NOT NULL,
    rows_inserted INT NOT NULL,
    type_coercion_failures TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stg_flight_prices_validated (
    source_row_num INT NOT NULL PRIMARY KEY,
    {_SOURCE_COLS_MYSQL},
    dq_status VARCHAR(10) NOT NULL,
    dq_flags VARCHAR(500),
    batch_id VARCHAR(250) NOT NULL,
    INDEX idx_validated_status (dq_status)
);

CREATE TABLE IF NOT EXISTS dq_issues (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id VARCHAR(250) NOT NULL,
    source_row_num INT NULL,
    rule_name VARCHAR(60) NOT NULL,
    column_name VARCHAR(60),
    original_value VARCHAR(255),
    severity VARCHAR(10) NOT NULL,
    action_taken VARCHAR(30) NOT NULL,
    INDEX idx_dq_rule (rule_name)
);

CREATE TABLE IF NOT EXISTS stg_flight_prices_enriched (
    {_cols(ENRICHED_COLUMNS, 0)},
    PRIMARY KEY (source_row_num),
    INDEX idx_enriched_airline (airline),
    INDEX idx_enriched_route (route)
);
""" + "".join(
    f"\nCREATE TABLE IF NOT EXISTS {name} (\n    {_cols(spec, 0)}\n);\n"
    for name, spec in KPI_TABLES.items()
)

PG_SCHEMA = "analytics"

POSTGRES_DDL = f"""
CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA};

CREATE TABLE IF NOT EXISTS {PG_SCHEMA}.fact_flight_prices (
    {_cols(ENRICHED_COLUMNS, 1)},
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_row_num)
);
CREATE INDEX IF NOT EXISTS idx_fact_airline ON {PG_SCHEMA}.fact_flight_prices (airline);
CREATE INDEX IF NOT EXISTS idx_fact_route ON {PG_SCHEMA}.fact_flight_prices (route);
CREATE INDEX IF NOT EXISTS idx_fact_season ON {PG_SCHEMA}.fact_flight_prices (season);

CREATE TABLE IF NOT EXISTS {PG_SCHEMA}.pipeline_run_log (
    batch_id VARCHAR(250) PRIMARY KEY,
    rows_in_file INTEGER,
    rows_valid INTEGER,
    rows_rejected INTEGER,
    rows_loaded INTEGER,
    dq_summary TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
""" + "".join(
    f"\nCREATE TABLE IF NOT EXISTS {PG_SCHEMA}.{name} (\n    {_cols(spec, 1)},\n"
    f"    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()\n);\n"
    for name, spec in KPI_TABLES.items()
) + f"""
CREATE OR REPLACE VIEW {PG_SCHEMA}.v_top_routes AS
    SELECT route_rank, route, source_name, destination_name, booking_count, avg_total_fare
    FROM {PG_SCHEMA}.kpi_popular_routes
    WHERE is_top_route
    ORDER BY route_rank;

CREATE OR REPLACE VIEW {PG_SCHEMA}.v_peak_vs_offpeak AS
    SELECT season_label, booking_count, avg_total_fare, pct_diff_vs_baseline
    FROM {PG_SCHEMA}.kpi_seasonal_fare_variation
    WHERE grouping_level = 'peak_flag';
"""
