"""Tests for the KPI report page, with made up data (no database)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dags"))

from flight_pipeline import report  # noqa: E402


def _data():
    return {
        "avg_fare": pd.DataFrame([
            {"airline": "Emirates", "booking_count": 10, "avg_total_fare": 1000.0, "median_total_fare": 900.0,
             "min_total_fare": 100.0, "max_total_fare": 2000.0, "fare_rank": 1},
            {"airline": "NovoAir <b>", "booking_count": 5, "avg_total_fare": 300.0, "median_total_fare": 250.0,
             "min_total_fare": 50.0, "max_total_fare": 600.0, "fare_rank": 2},
        ]),
        "seasonal": pd.DataFrame([
            {"grouping_level": "season", "season_label": "Regular", "is_peak_season": False, "booking_count": 10,
             "avg_total_fare": 500.0, "pct_diff_vs_baseline": 0.0},
            {"grouping_level": "season", "season_label": "Eid", "is_peak_season": True, "booking_count": 5,
             "avg_total_fare": 650.0, "pct_diff_vs_baseline": 30.0},
            {"grouping_level": "peak_flag", "season_label": "Peak", "is_peak_season": True, "booking_count": 5,
             "avg_total_fare": 650.0, "pct_diff_vs_baseline": 30.0},
            {"grouping_level": "peak_flag", "season_label": "Non-Peak", "is_peak_season": False, "booking_count": 10,
             "avg_total_fare": 500.0, "pct_diff_vs_baseline": 0.0},
        ]),
        "bookings": pd.DataFrame([
            {"airline": "Emirates", "booking_count": 10, "booking_share_pct": 66.67, "booking_rank": 1},
            {"airline": "NovoAir <b>", "booking_count": 5, "booking_share_pct": 33.33, "booking_rank": 2},
        ]),
        "routes": pd.DataFrame([
            {"route_rank": 1, "route": "DAC-DXB", "source_name": "Dhaka", "destination_name": "Dubai",
             "booking_count": 8, "avg_total_fare": 900.0},
        ]),
        "overall_avg": 766.7,
        "run": {"batch_id": "manual__test", "rows_in_file": 15, "rows_valid": 15, "rows_rejected": 0,
                "rows_loaded": 15, "loaded_at": datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)},
    }


def test_render_html_has_all_sections_and_numbers():
    page = report.render_html(_data(), datetime(2026, 11, 11, 12, 5, tzinfo=timezone.utc))
    for text in ["Average fare by airline", "Seasonal fare variation", "Booking count by airline",
                 "Most popular routes", "+30.0%", "DAC-DXB", "manual__test", "Show the numbers as tables"]:
        assert text in page
    assert page.count('<svg class="chart"') == 4
    assert "NovoAir &lt;b&gt;" in page and "NovoAir <b>" not in page      # html in a name must not break the page
    assert "<script src" not in page and "<link" not in page               # no external files, it has to work offline


def test_write_report_is_atomic(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "fetch_report_data", lambda conn: _data())
    info = report.write_report(None, str(tmp_path))
    out = tmp_path / "kpi_report.html"
    assert out.exists() and info["path"] == str(out) and info["airlines"] == 2
    assert not (tmp_path / "kpi_report.html.tmp").exists()


def test_nice_max():
    assert report._nice_max(179_420) == 200_000
    assert report._nice_max(811) == 1000
    assert report._nice_max(94_923) == 100_000
