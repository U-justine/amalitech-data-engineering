"""Makes a FAKE csv with the same columns as the Kaggle file, only for testing.

I used this while I didn't have the Kaggle data yet. For the real analysis use
the real file (data/Flight_Price_Dataset_of_Bangladesh.csv), not this one.

About 1% of the rows are broken on purpose (empty values, negative fares, bad
airport codes, wrong totals, lowercase codes, duplicates) so I could check that
the validation step catches them.

python scripts/generate_sample_data.py [--rows 57000] [--out data/Flight_Price_Dataset_of_Bangladesh.csv]
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta

AIRPORTS = {
    "DAC": "Hazrat Shahjalal International Airport, Dhaka",
    "CGP": "Shah Amanat International Airport, Chittagong",
    "ZYL": "Osmani International Airport, Sylhet",
    "CXB": "Cox's Bazar Airport",
    "JSR": "Jessore Airport",
    "RJH": "Shah Makhdum Airport, Rajshahi",
    "SPD": "Saidpur Airport",
    "BZL": "Barisal Airport",
    "DXB": "Dubai International Airport",
    "JED": "King Abdulaziz International Airport, Jeddah",
    "KUL": "Kuala Lumpur International Airport",
    "BKK": "Suvarnabhumi Airport, Bangkok",
    "SIN": "Singapore Changi Airport",
    "DOH": "Hamad International Airport, Doha",
    "LHR": "London Heathrow Airport",
    "CCU": "Netaji Subhas Chandra Bose International Airport, Kolkata",
    "DEL": "Indira Gandhi International Airport, Delhi",
    "IST": "Istanbul Airport",
    "YYZ": "Toronto Pearson International Airport",
    "JFK": "John F. Kennedy International Airport, New York",
}
DOMESTIC = ["DAC", "CGP", "ZYL", "CXB", "JSR", "RJH", "SPD", "BZL"]
INTERNATIONAL = [a for a in AIRPORTS if a not in DOMESTIC]
AIRLINES = {
    "US-Bangla Airlines": 1.0, "Biman Bangladesh Airlines": 1.1, "NovoAir": 0.95, "Air Astra": 0.9,
    "Emirates": 1.5, "Qatar Airways": 1.45, "Singapore Airlines": 1.4, "Turkish Airlines": 1.35,
    "Saudia": 1.2, "Malaysian Airlines": 1.15, "Air Arabia": 0.85, "FlyDubai": 0.9,
    "IndiGo": 0.8, "Thai Airways": 1.2, "Cathay Pacific": 1.4,
}
DOMESTIC_AIRLINES = ["US-Bangla Airlines", "Biman Bangladesh Airlines", "NovoAir", "Air Astra"]
AIRCRAFT = ["Boeing 737", "Boeing 777", "Boeing 787", "Airbus A320", "Airbus A350", "ATR 72", "Dash 8"]
CLASSES = {"Economy": 1.0, "Business": 2.8, "First Class": 4.5}
BOOKING = ["Online Website", "Travel Agency", "Direct Booking"]
SEASON_MULT = {"Regular": 1.0, "Eid": 1.35, "Hajj": 1.5, "Winter Holidays": 1.2}

HEADER = ["Airline", "Source", "Source Name", "Destination", "Destination Name",
          "Departure Date & Time", "Arrival Date & Time", "Duration (hrs)", "Stopovers",
          "Aircraft Type", "Class", "Booking Source", "Base Fare (BDT)", "Tax & Surcharge (BDT)",
          "Total Fare (BDT)", "Seasonality", "Days Before Departure"]


def season_for(d: datetime) -> str:
    eids = [datetime(2025, 3, 31), datetime(2025, 6, 7)]
    if any(timedelta(days=-7) <= d - e <= timedelta(days=3) for e in eids):
        return "Eid"
    if datetime(2025, 5, 15) <= d <= datetime(2025, 6, 5):
        return "Hajj"
    if (d.month == 12 and d.day >= 10) or (d.month == 1 and d.day <= 15):
        return "Winter Holidays"
    return "Regular"


def make_row(rng: random.Random) -> list:
    if rng.random() < 0.55:
        src, dst = rng.sample(DOMESTIC, 2)
        airline = rng.choice(DOMESTIC_AIRLINES)
        hrs = rng.uniform(0.5, 1.5)
        base = rng.uniform(3000, 12000)
        stop = "Direct"
    else:
        a, b = "DAC" if rng.random() < 0.7 else rng.choice(["CGP", "ZYL"]), rng.choice(INTERNATIONAL)
        src, dst = (a, b) if rng.random() < 0.5 else (b, a)
        airline = rng.choice(list(AIRLINES))
        hrs = rng.uniform(2, 20)
        base = rng.uniform(15000, 120000)
        stop = rng.choice(["Direct", "1 Stop", "2 Stops"])
    dep = datetime(2025, 1, 1) + timedelta(minutes=rng.randrange(0, 365 * 24 * 60, 5))
    season = season_for(dep)
    cls = rng.choices(list(CLASSES), weights=[80, 15, 5])[0]
    base *= AIRLINES[airline] * CLASSES[cls] * SEASON_MULT[season]
    tax = base * rng.uniform(0.08, 0.2) + rng.choice([0, 500, 1000])
    return [airline, src, AIRPORTS[src], dst, AIRPORTS[dst], dep.strftime("%Y-%m-%d %H:%M:%S"),
            (dep + timedelta(hours=hrs)).strftime("%Y-%m-%d %H:%M:%S"), round(hrs, 6), stop,
            rng.choice(AIRCRAFT), cls, rng.choice(BOOKING), round(base, 2), round(tax, 2),
            round(base + tax, 2), season, rng.randint(1, 90)]


def dirty(row: list, rng: random.Random) -> list:
    kind = rng.choice(["null_airline", "neg_fare", "bad_city", "mismatch", "lower_code",
                       "null_tax", "same_city", "text_fare", "null_total", "null_season"])
    if kind == "null_airline":
        row[0] = ""
    elif kind == "neg_fare":
        row[12] = -abs(row[12])
    elif kind == "bad_city":
        row[1] = rng.choice(["Dhaka", "XX", "12A"])
    elif kind == "mismatch":
        row[14] = round(row[14] * 1.1, 2)
    elif kind == "lower_code":
        row[3] = " " + row[3].lower()
    elif kind == "null_tax":
        row[13] = ""
    elif kind == "same_city":
        row[3], row[4] = row[1], row[2]
    elif kind == "text_fare":
        row[12] = "N/A"
    elif kind == "null_total":
        row[14] = ""
    elif kind == "null_season":
        row[15] = ""
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=57_000)
    ap.add_argument("--out", default="data/Flight_Price_Dataset_of_Bangladesh.csv")
    ap.add_argument("--dirty-ratio", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    rows = []
    for _ in range(args.rows):
        r = make_row(rng)
        if rng.random() < args.dirty_ratio:
            r = dirty(r, rng)
        rows.append(r)
    for _ in range(int(args.rows * 0.001)):       # add some duplicate rows too
        rows.append(list(rng.choice(rows)))
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
