"""Downloads the Kaggle "Flight Price Dataset of Bangladesh" into data/.

You need kaggle.json (your Kaggle API key) in %USERPROFILE%\\.kaggle\\ on Windows,
~/.kaggle/ on Mac/Linux, or in the folder KAGGLE_CONFIG_DIR points to.
More help: docs/KAGGLE_SETUP.md

The download was slow for me sometimes, so:
  - it downloads into data/.download/ first and only moves the csv into data/
    when it's complete and has the right columns. Airflow never sees half a file
  - network errors are retried (3 times by default, --retries to change)
  - if data/ already has a good file it doesn't download again, unless --force

Use it from the project folder with the venv active:
    python scripts/download_data.py            # download if it's not there yet
    python scripts/download_data.py --force    # download again and replace it
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import sys
import time

DATASET = "mahatiratusher/flight-price-dataset-of-bangladesh"
TARGET_NAME = "Flight_Price_Dataset_of_Bangladesh.csv"
EXPECTED_COLUMNS = ["Airline", "Source", "Destination", "Base Fare", "Tax & Surcharge", "Total Fare"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
TMP_DIR = os.path.join(DATA_DIR, ".download")
TARGET = os.path.join(DATA_DIR, TARGET_NAME)


def check_csv(path: str) -> int:
    """returns the number of rows, or ValueError if the columns are wrong"""
    with open(path, encoding="utf-8-sig") as fh:
        header = fh.readline()
        rows = sum(1 for line in fh if line.strip())
    missing = [c for c in EXPECTED_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"missing expected columns {missing}")
    if rows == 0:
        raise ValueError("file has no data rows")
    return rows


def authenticate():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        sys.exit(f"[FAIL] Kaggle package missing ({exc}).\n"
                 "       Run: pip install -r requirements-dev.txt")
    api = KaggleApi()
    try:
        api.authenticate()
    except Exception as exc:
        sys.exit(f"[FAIL] Kaggle login failed: {exc}\n"
                 "       Put kaggle.json in %USERPROFILE%\\.kaggle\\ or set KAGGLE_CONFIG_DIR. "
                 "See docs/KAGGLE_SETUP.md")
    print("[OK]   Kaggle login")
    return api


def download(api, retries: int) -> str:
    """download + unzip into TMP_DIR, retry on errors. returns the path of the csv"""
    for attempt in range(1, retries + 1):
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        os.makedirs(TMP_DIR, exist_ok=True)
        try:
            print(f"[..]   Downloading {DATASET} (attempt {attempt}/{retries}) - this can take a few minutes")
            started = time.time()
            api.dataset_download_files(DATASET, path=TMP_DIR, unzip=True, force=True, quiet=False)
            csvs = glob.glob(os.path.join(TMP_DIR, "**", "*.csv"), recursive=True)
            if not csvs:
                raise RuntimeError("download finished but no CSV was found")
            print(f"[OK]   Downloaded in {time.time() - started:.0f}s")
            return csvs[0]
        except KeyboardInterrupt:
            shutil.rmtree(TMP_DIR, ignore_errors=True)
            sys.exit("\n[STOP] Cancelled. Nothing was changed in data/.")
        except Exception as exc:
            wait = 15 * attempt
            print(f"[WARN] Attempt {attempt} failed: {type(exc).__name__}: {exc}")
            if attempt == retries:
                shutil.rmtree(TMP_DIR, ignore_errors=True)
                sys.exit("[FAIL] Download failed after all retries. Nothing was changed in data/.\n"
                         "       Check your internet, or download by hand (docs/KAGGLE_SETUP.md, option C).")
            print(f"       Retrying in {wait}s ...")
            time.sleep(wait)
    raise AssertionError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="download again even if data/ already has the file")
    ap.add_argument("--retries", type=int, default=3, help="download attempts on network errors (default 3)")
    args = ap.parse_args()

    if os.path.exists(TARGET) and not args.force:
        try:
            rows = check_csv(TARGET)
            print(f"[OK]   {TARGET} already exists ({rows:,} rows). Use --force to download again.")
            return
        except ValueError as exc:
            print(f"[WARN] Existing file is not usable ({exc}); downloading a fresh copy.")

    api = authenticate()
    downloaded = download(api, max(1, args.retries))

    try:
        rows = check_csv(downloaded)
    except ValueError as exc:
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        sys.exit(f"[FAIL] Downloaded file is not the expected dataset: {exc}. Nothing was changed in data/.")

    os.replace(downloaded, TARGET)          # one step, so Airflow sees the old file or the new one
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    print(f"[OK]   Saved {TARGET} ({rows:,} rows)")
    print("Next:  docker compose exec airflow-scheduler airflow dags trigger flight_price_pipeline")


if __name__ == "__main__":
    main()
