"""Tests for the watermark decision (no database needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dags"))

from flight_pipeline import watermark  # noqa: E402

MD5 = "a" * 32
STORED = {"file_md5": MD5, "batch_id": "manual__1", "updated_at": "2026-11-12 10:00"}


def test_first_run_goes_ahead():
    run, reason = watermark.should_run(MD5, None)
    assert run and "first run" in reason


def test_same_file_is_skipped():
    run, reason = watermark.should_run(MD5, STORED)
    assert not run and "skipping" in reason and "manual__1" in reason


def test_changed_file_goes_ahead():
    run, reason = watermark.should_run("b" * 32, STORED)
    assert run and "changed" in reason


def test_force_ignores_the_watermark():
    run, reason = watermark.should_run(MD5, STORED, force=True)
    assert run and "force" in reason
