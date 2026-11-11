"""Settings for the flight price pipeline.

I put all the values I might want to change in one place (connection ids,
validation limits, season dates, alert thresholds) so I don't have to dig
through the DAG or the task code to find them.
"""
from __future__ import annotations

import os
from datetime import date

# --- connections and paths ---
MYSQL_CONN_ID = "mysql_staging"
POSTGRES_CONN_ID = "postgres_analytics"
CSV_PATH = os.getenv(
    "FLIGHT_CSV_PATH", "/opt/airflow/data/Flight_Price_Dataset_of_Bangladesh.csv"
)
INSERT_CHUNK_SIZE = 5_000

# --- columns of the CSV ---
# column name -> (MySQL type, how I parse it in pandas)
# the names are the cleaned-up header names, e.g. "Base Fare (BDT)" becomes base_fare
# (see normalize_column_name in ingestion.py)
SOURCE_SCHEMA: dict[str, tuple[str, str]] = {
    "airline": ("VARCHAR(100)", "str"),
    "source": ("VARCHAR(10)", "str"),
    "source_name": ("VARCHAR(150)", "str"),
    "destination": ("VARCHAR(10)", "str"),
    "destination_name": ("VARCHAR(150)", "str"),
    "departure_date_time": ("DATETIME", "datetime"),
    "arrival_date_time": ("DATETIME", "datetime"),
    "duration_hrs": ("DECIMAL(8,4)", "float"),
    "stopovers": ("VARCHAR(30)", "str"),
    "aircraft_type": ("VARCHAR(60)", "str"),
    "travel_class": ("VARCHAR(30)", "str"),
    "booking_source": ("VARCHAR(60)", "str"),
    "base_fare": ("DECIMAL(14,2)", "float"),
    "tax_surcharge": ("DECIMAL(14,2)", "float"),
    "total_fare": ("DECIMAL(14,2)", "float"),
    "seasonality": ("VARCHAR(40)", "str"),
    "days_before_departure": ("INT", "int"),
}

# other spellings of some headers, just in case the file changes a bit
COLUMN_ALIASES = {
    "class": "travel_class",
    "tax_and_surcharge": "tax_surcharge",
    "tax_surcharges": "tax_surcharge",
    "departure_datetime": "departure_date_time",
    "arrival_datetime": "arrival_date_time",
    "duration": "duration_hrs",
    "season": "seasonality",
}

# required columns from the project brief.
# total_fare is in the list but I can calculate it (base + tax) if it's missing,
# so a missing total_fare only gives a warning
REQUIRED_COLUMNS = ["airline", "source", "destination", "base_fare", "tax_surcharge", "total_fare"]
DERIVABLE_COLUMNS = {"total_fare"}
CATEGORICAL_REQUIRED = ["airline", "source", "destination"]
FARE_COLUMNS = ["base_fare", "tax_surcharge", "total_fare"]

# --- validation ---
IATA_PATTERN = r"^[A-Z]{3}$"
# airports I found in the dataset. a code that's not here only gets a warning,
# I don't want to throw away a route just because it's new
KNOWN_AIRPORTS = {
    # Domestic
    "DAC", "CGP", "ZYL", "CXB", "JSR", "RJH", "SPD", "BZL",
    # International
    "DXB", "JED", "KUL", "BKK", "SIN", "DOH", "LHR", "CCU", "DEL", "IST", "YYZ", "JFK",
}
TOTAL_FARE_TOLERANCE = 1.0          # in BDT, allows for small rounding differences
MAX_REJECT_RATIO = float(os.getenv("FLIGHT_MAX_REJECT_RATIO", "0.05"))  # more than 5% bad rows -> stop the run

# --- seasons ---
REGULAR_SEASON = "Regular"
SEASON_ALIASES = {
    "regular": "Regular",
    "normal": "Regular",
    "off peak": "Regular",
    "eid": "Eid",
    "eid ul fitr": "Eid",
    "eid ul adha": "Eid",
    "eid al fitr": "Eid",
    "eid al adha": "Eid",
    "hajj": "Hajj",
    "winter": "Winter Holidays",
    "winter holidays": "Winter Holidays",
    "winter holiday": "Winter Holidays",
}

# only used when a row has no Seasonality value.
# Eid dates in Bangladesh (approximate, they depend on the moon)
EID_DATES = [
    date(2023, 4, 22), date(2023, 6, 29),
    date(2024, 4, 11), date(2024, 6, 17),
    date(2025, 3, 31), date(2025, 6, 7),
    date(2026, 3, 21), date(2026, 5, 27),
]
EID_WINDOW_DAYS_BEFORE = 7
EID_WINDOW_DAYS_AFTER = 3
WINTER_HOLIDAY_WINDOW = ((12, 10), (1, 15))   # 10 Dec to 15 Jan

TOP_ROUTES_LIMIT = 10

# --- alerts (all in seconds) ---
# slower than the threshold -> task still succeeds, but I get a SLOW TASK email
# over the timeout -> task is killed, fails, and I get a TIMED OUT email
# normally (57k rows): extract ~5s, validate ~5s, load_to_postgres ~2-4s
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


SLOW_TASK_DEFAULT_SECONDS = _env_int("ALERT_SLOW_TASK_SECONDS", 300)
# use the task name without the group, so "load_to_postgres" not "load.load_to_postgres"
SLOW_TASK_THRESHOLDS = {
    "extract_csv_to_mysql": _env_int("ALERT_SLOW_EXTRACT_SECONDS", 120),
    "load_to_postgres": _env_int("ALERT_SLOW_LOAD_SECONDS", 120),
}
SLOW_RUN_THRESHOLD_SECONDS = _env_int("ALERT_SLOW_RUN_SECONDS", 900)

DEFAULT_TASK_TIMEOUT_SECONDS = _env_int("TASK_TIMEOUT_SECONDS", 1800)
LOAD_TIMEOUT_SECONDS = _env_int("LOAD_TIMEOUT_SECONDS", 600)

# --- retries ---
# db / network problems: retry with backoff (1 min, 2 min, 4 min, max 10 min)
# missing csv: retry every 5 min, the file might just be late
# bad data: no retry at all (AirflowFailException), retrying won't fix the data
TASK_RETRIES = _env_int("TASK_RETRIES", 3)
RETRY_DELAY_SECONDS = _env_int("RETRY_DELAY_SECONDS", 60)
MAX_RETRY_DELAY_SECONDS = _env_int("MAX_RETRY_DELAY_SECONDS", 600)
SOURCE_FILE_RETRIES = _env_int("SOURCE_FILE_RETRIES", 3)
SOURCE_FILE_RETRY_DELAY_SECONDS = _env_int("SOURCE_FILE_RETRY_DELAY_SECONDS", 300)
NOTIFY_RETRIES = _env_int("NOTIFY_RETRIES", 1)
DAGRUN_TIMEOUT_SECONDS = _env_int("DAGRUN_TIMEOUT_SECONDS", 3600)

# retries and failures also get written here, in case the email doesn't go out
ALERT_LOG_PATH = os.getenv("ALERT_LOG_PATH", os.path.join(os.path.dirname(CSV_PATH), "alerts.log"))
# where the KPI report (html with the charts) is saved
REPORT_DIR = os.getenv("FLIGHT_REPORT_DIR", os.path.join(os.path.dirname(CSV_PATH), "reports"))

ALERT_EMAIL_ON_RETRY = os.getenv("ALERT_EMAIL_ON_RETRY", "false").lower() == "true"
# default for the send_success_email param (the daily scheduled run uses this)
ALERT_EMAIL_ON_SUCCESS = os.getenv("ALERT_EMAIL_ON_SUCCESS", "false").lower() == "true"
