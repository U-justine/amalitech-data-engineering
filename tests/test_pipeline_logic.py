"""Tests for the validation / transform / KPI code. Only pandas, no Airflow or database.

pip install -r requirements-dev.txt
pytest -q
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dags"))

from flight_pipeline import config, ingestion, kpis, transformation, validation  # noqa: E402


def _row(i, **kw):
    base = {
        "source_row_num": i, "airline": "US-Bangla Airlines", "source": "DAC", "source_name": "Dhaka",
        "destination": "CGP", "destination_name": "Chittagong",
        "departure_date_time": pd.Timestamp("2025-03-28 10:00"), "arrival_date_time": pd.Timestamp("2025-03-28 11:00"),
        "duration_hrs": 1.0, "stopovers": "Direct", "aircraft_type": "ATR 72", "travel_class": "Economy",
        "booking_source": "Online Website", "base_fare": 5000.0, "tax_surcharge": 700.0, "total_fare": 5700.0,
        "seasonality": "Regular", "days_before_departure": 10,
    }
    base.update(kw)
    return base


@pytest.mark.parametrize("raw,expected", [
    ("Base Fare (BDT)", "base_fare"),
    ("Tax & Surcharge (BDT)", "tax_surcharge"),
    ("Total Fare (BDT)", "total_fare"),
    ("Departure Date & Time", "departure_date_time"),
    ("Duration (hrs)", "duration_hrs"),
    ("Class", "travel_class"),
    (" Airline ", "airline"),
    ("Tax & Surcharge", "tax_surcharge"),
])
def test_normalize_column_name(raw, expected):
    assert ingestion.normalize_column_name(raw) == expected


def test_coerce_types_counts_failures():
    raw = pd.DataFrame({"base_fare": ["100", "abc", None], "days_before_departure": ["5", "x", "7"]})
    typed, failures = ingestion.coerce_types(raw)
    assert typed["base_fare"].iloc[0] == 100.0 and pd.isna(typed["base_fare"].iloc[1])
    assert failures == {"base_fare": 1, "days_before_departure": 1}
    assert typed["airline"].isna().all()          # column that's not in the input should come back as NULL


def test_required_columns():
    with pytest.raises(validation.DataQualityError):
        validation.check_required_columns(["airline", "source", "destination", "base_fare"])
    res = validation.check_required_columns(["airline", "source", "destination", "base_fare", "tax_surcharge"])
    assert res["derivable_missing"] == ["total_fare"]


def test_validation_rules():
    df = pd.DataFrame([
        _row(1),                                             # valid
        _row(2, airline=None),                               # missing airline -> reject
        _row(3, base_fare=-10.0),                            # negative -> reject
        _row(4, source="Dhaka"),                             # invalid code -> reject
        _row(5, destination=" cgp"),                         # corrected -> valid
        _row(6, destination="DAC"),                          # same src/dst -> reject
        _row(7, tax_surcharge=None),                         # imputed from total -> valid
        _row(8, total_fare=9999.0),                          # mismatch -> valid (warning)
        _row(9, base_fare=None, total_fare=None),            # base and total both missing, can't fix -> reject
        _row(10, destination="XYZ"),                         # looks like a code but not in my list -> only a warning
    ])
    res = validation.validate_rows(df)
    status = dict(zip(res.validated["source_row_num"], res.validated["dq_status"]))
    assert [k for k, v in status.items() if v == "rejected"] == [2, 3, 4, 6, 9]
    v = res.validated.set_index("source_row_num")
    assert v.loc[5, "destination"] == "CGP"
    assert v.loc[7, "tax_surcharge"] == 700.0
    rules = set(res.issues["rule_name"])
    assert {"missing_required_value", "negative_fare", "invalid_airport_code", "airport_code_corrected",
            "same_source_destination", "missing_fare_imputed", "total_fare_mismatch", "missing_fare",
            "unknown_airport_code"} <= rules
    assert res.summary["rows_rejected"] == 5


def test_quality_gate():
    validation.enforce_quality_gate({"rows_checked": 100, "rows_valid": 99, "reject_ratio": 0.01})
    with pytest.raises(validation.DataQualityError):
        validation.enforce_quality_gate({"rows_checked": 100, "rows_valid": 50, "reject_ratio": 0.5})


def test_transform_recalculates_total_and_season():
    df = pd.DataFrame([
        _row(1),
        _row(2, total_fare=9999.0),
        _row(3, total_fare=None, seasonality=None),   # 2025-03-28 is in the Eid window
        _row(4, seasonality="eid-ul-fitr"),
        _row(5, airline=None),
    ])
    df["dq_status"] = ["valid", "valid", "valid", "valid", "rejected"]
    out = transformation.transform(df, "b1").set_index("source_row_num")
    assert len(out) == 4
    assert out.loc[2, "total_fare"] == 5700.0 and out.loc[2, "total_fare_recalculated"]
    assert out.loc[3, "total_fare"] == 5700.0
    assert out.loc[3, "season"] == "Eid" and out.loc[3, "season_source"] == "derived"
    assert out.loc[4, "season"] == "Eid" and out.loc[4, "is_peak_season"]
    assert not out.loc[1, "is_peak_season"]
    assert out.loc[1, "route"] == "DAC-CGP"
    assert (out["total_fare"] == out["base_fare"] + out["tax_surcharge"]).all()


def test_derive_season_winter():
    assert transformation.derive_season(pd.Timestamp("2025-12-20")) == "Winter Holidays"
    assert transformation.derive_season(pd.Timestamp("2025-01-10")) == "Winter Holidays"
    assert transformation.derive_season(pd.Timestamp("2025-08-10")) == "Regular"


def _enriched():
    rows = [
        _row(1, airline="A", total_fare=100.0, base_fare=90.0, tax_surcharge=10.0, seasonality="Regular"),
        _row(2, airline="A", total_fare=200.0, base_fare=180.0, tax_surcharge=20.0, seasonality="Eid"),
        _row(3, airline="B", total_fare=300.0, base_fare=270.0, tax_surcharge=30.0, seasonality="Regular",
             source="DAC", destination="DXB"),
    ]
    df = pd.DataFrame(rows)
    df["dq_status"] = "valid"
    return transformation.transform(df, "b1")


def test_kpis():
    e = _enriched()
    avg = kpis.avg_fare_by_airline(e, "b1").set_index("airline")
    assert avg.loc["A", "avg_total_fare"] == 150.0 and avg.loc["B", "fare_rank"] == 1

    cnt = kpis.booking_count_by_airline(e, "b1").set_index("airline")
    assert cnt.loc["A", "booking_count"] == 2 and cnt["booking_share_pct"].sum() == pytest.approx(100, abs=0.1)

    seas = kpis.seasonal_fare_variation(e, "b1")
    peak = seas[(seas.grouping_level == "peak_flag") & (seas.season_label == "Peak")].iloc[0]
    assert peak.avg_total_fare == 200.0
    assert peak.pct_diff_vs_baseline == 0.0          # regular avg = (100+300)/2 = 200

    routes = kpis.popular_routes(e, "b1")
    assert routes.iloc[0]["route"] == "DAC-CGP" and routes.iloc[0]["booking_count"] == 2
    assert routes["route_rank"].tolist() == [1, 2]
