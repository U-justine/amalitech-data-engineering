#!/usr/bin/env python3
"""
data_generator.py
-----------------
Simulates an e-commerce platform by writing batches of fake user-activity
events (views, add-to-carts, purchases) as CSV files into a folder that the
Spark Structured Streaming job watches.

Each file is first written to a hidden staging folder and then atomically
renamed into the watched folder, so Spark never picks up a half-written file.

Optionally injects a small share of "dirty" rows (bad prices, unknown event
types, missing IDs, malformed timestamps, duplicates) so the Spark cleaning
logic can be tested.

Usage examples
    python data_generator.py                              # 20 files x 100 events, 2s apart
    python data_generator.py --files 0 --interval 1       # run forever, 1 file/sec
    python data_generator.py --events-per-file 1000 --dirty-rate 0.05
"""

import argparse
import csv
import os
import random
import time
import uuid
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))   # project folder

CSV_HEADER = [
    "event_id",
    "user_id",
    "session_id",
    "event_type",
    "product_id",
    "product_name",
    "category",
    "price",
    "quantity",
    "device",
    "event_timestamp",
]

# A small, fixed product catalogue so prices/categories are consistent per product.
CATALOGUE = {
    "Electronics": [("Wireless Earbuds", 59.99), ("Smartphone", 499.00), ("USB-C Charger", 19.99),
                    ("Bluetooth Speaker", 39.50), ("Laptop Stand", 29.95)],
    "Fashion": [("Running Shoes", 89.90), ("Denim Jacket", 74.00), ("Cotton T-Shirt", 14.99),
                ("Leather Belt", 24.50)],
    "Home & Kitchen": [("Coffee Maker", 79.00), ("Non-stick Pan", 34.99), ("Blender", 49.99),
                       ("Table Lamp", 22.00)],
    "Books": [("Data Engineering Handbook", 39.99), ("Mystery Novel", 12.50), ("Cookbook", 18.75)],
    "Beauty": [("Face Moisturiser", 16.99), ("Shampoo", 8.49), ("Perfume", 65.00)],
}
PRODUCTS = []
for cat, items in CATALOGUE.items():
    for name, price in items:
        PRODUCTS.append({"product_id": f"P{len(PRODUCTS) + 1:04d}", "product_name": name,
                         "category": cat, "price": price})

# Realistic funnel: most events are views, fewer carts, fewer purchases.
EVENT_TYPES = ["view", "add_to_cart", "purchase"]
EVENT_WEIGHTS = [0.70, 0.20, 0.10]
DEVICES = ["mobile", "desktop", "tablet"]
DEVICE_WEIGHTS = [0.60, 0.32, 0.08]


# Returns the current time in UTC as text, e.g. 2026-11-03 10:15:42.123.
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


# Creates one fake shopper action (view, add to cart or purchase) for a random user and product.
def make_event(user_pool: int) -> dict:
    product = random.choice(PRODUCTS)
    event_type = random.choices(EVENT_TYPES, EVENT_WEIGHTS)[0]
    quantity = random.randint(1, 3) if event_type != "view" else 1
    return {
        "event_id": str(uuid.uuid4()),
        "user_id": f"U{random.randint(1, user_pool):05d}",
        "session_id": uuid.uuid4().hex[:12],
        "event_type": event_type,
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "category": product["category"],
        "price": f"{product['price']:.2f}",
        "quantity": quantity,
        "device": random.choices(DEVICES, DEVICE_WEIGHTS)[0],
        "event_timestamp": now_iso(),
    }


# Breaks an event on purpose (negative price, bad date, missing user...) to test the cleaning.
# One case only changes letter case/spaces, so Spark should fix and keep that row.
def make_dirty(event: dict, previous: list) -> dict:
    kind = random.choice(["neg_price", "bad_type", "no_user", "bad_ts", "messy_case", "duplicate",
                          "bad_qty"])
    e = dict(event)
    if kind == "neg_price":
        e["price"] = "-5.00"
    elif kind == "bad_type":
        e["event_type"] = "click??"
    elif kind == "no_user":
        e["user_id"] = ""
    elif kind == "bad_ts":
        e["event_timestamp"] = "not-a-timestamp"
    elif kind == "messy_case":          # valid but needs normalising -> should be KEPT
        e["event_type"] = f"  {e['event_type'].upper()} "
    elif kind == "duplicate" and previous:
        return dict(random.choice(previous))   # exact copy of an earlier row
    elif kind == "bad_qty":
        e["quantity"] = "abc"
    return e


# Saves a list of events as a CSV file: written to .staging first, then moved into data/input
# in one step so Spark never reads a half-written file.
def write_batch(rows: list, out_dir: str, staging_dir: str, file_no: int) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    fname = f"events_{ts}_{file_no:05d}.csv"
    tmp_path = os.path.join(staging_dir, fname)
    final_path = os.path.join(out_dir, fname)
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, final_path)          # atomic on the same filesystem
    return final_path


# Starting point: reads the options, then writes a new CSV file every few seconds until done.
def main() -> None:
    p = argparse.ArgumentParser(description="Generate fake e-commerce event CSV files.")
    p.add_argument("--output-dir", default=os.getenv("INPUT_DIR", os.path.join(ROOT, "data", "input")),
                   help="Folder watched by Spark (default: data/input)")
    p.add_argument("--files", type=int, default=20, help="Number of files to write (0 = forever)")
    p.add_argument("--events-per-file", type=int, default=100)
    p.add_argument("--interval", type=float, default=2.0, help="Seconds between files")
    p.add_argument("--users", type=int, default=5000, help="Size of the simulated user base")
    p.add_argument("--dirty-rate", type=float, default=0.0,
                   help="Share of rows to corrupt for testing, e.g. 0.05 (default 0)")
    p.add_argument("--seed", type=int, default=None, help="Random seed for reproducible runs")
    args = p.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    out_dir = os.path.abspath(args.output_dir)
    staging_dir = os.path.join(os.path.dirname(out_dir), ".staging")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(staging_dir, exist_ok=True)

    print(f"[generator] writing to {out_dir} | {args.events_per_file} events/file | "
          f"interval {args.interval}s | dirty-rate {args.dirty_rate}")
    file_no, total = 0, 0
    try:
        while args.files == 0 or file_no < args.files:
            file_no += 1
            rows = []
            for _ in range(args.events_per_file):
                ev = make_event(args.users)
                if args.dirty_rate and random.random() < args.dirty_rate:
                    ev = make_dirty(ev, rows)
                rows.append(ev)
            path = write_batch(rows, out_dir, staging_dir, file_no)
            total += len(rows)
            print(f"[generator] file {file_no}: {os.path.basename(path)} ({len(rows)} rows, total {total})")
            if args.files == 0 or file_no < args.files:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    print(f"[generator] done: {file_no} files, {total} events")


if __name__ == "__main__":
    main()
