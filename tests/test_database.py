# Tests for database.py and the rules in sql/schema.sql, including failures.
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg2
import pytest

from pulseguard.storage import database
from pulseguard.storage.database import save_batch

GOOD = {"customer_id": "CUST-A", "recorded_at": "2026-01-01T12:00:00+00:00", "heart_rate": 70, "status": "normal"}


def reading(**changes):
    return {**GOOD, **changes}


def count_rows(db, table):
    with db.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")
        return cur.fetchone()[0]


# ---------------------------------------------------------------- good cases

def test_save_good_and_rejected(db):
    saved = save_batch(db, [reading()], [("bad message", "invalid_json")])
    assert saved == 1
    assert count_rows(db, "readings") == 1
    assert count_rows(db, "rejected_readings") == 1


def test_duplicate_is_skipped_not_an_error(db):
    assert save_batch(db, [reading()], []) == 1
    assert save_batch(db, [reading()], []) == 0   # same customer + time
    assert count_rows(db, "readings") == 1


def test_database_works_out_seconds_per_step(db):
    """Given sent and received times, PostgreSQL fills in the seconds for each step."""
    now = datetime.now(timezone.utc)
    save_batch(db, [reading(sent_at=now - timedelta(seconds=0.25), received_at=now - timedelta(seconds=0.05))], [])
    with db.cursor() as cur:
        cur.execute("SELECT kafka_seconds, save_seconds, total_seconds FROM readings")
        kafka_seconds, save_seconds, total_seconds = cur.fetchone()
    assert kafka_seconds == Decimal("0.200")        # 0.25 s - 0.05 s
    assert 0.04 <= save_seconds < 5                  # received 0.05 s ago, saved just now
    assert total_seconds == kafka_seconds + save_seconds


def test_reading_without_timing_still_saves(db):
    """Old or test messages may have no sent time: the row is saved, the seconds are just empty."""
    save_batch(db, [reading()], [])
    with db.cursor() as cur:
        cur.execute("SELECT kafka_seconds, total_seconds FROM readings")
        assert cur.fetchone() == (None, None)


def test_timing_per_minute_view(db):
    now = datetime.now(timezone.utc)
    rows = [reading(customer_id=f"C{i}", sent_at=now - timedelta(seconds=1), received_at=now) for i in range(3)]
    save_batch(db, rows, [])
    with db.cursor() as cur:
        cur.execute("SELECT readings, avg_kafka_seconds FROM timing_per_minute")
        count, avg_kafka = cur.fetchone()
    assert count == 3 and avg_kafka == Decimal("1.000")


# ---------------------------------------------------------------- error cases

@pytest.mark.parametrize("bad", [
    pytest.param(reading(heart_rate=500), id="heart rate above 230"),
    pytest.param(reading(heart_rate=0), id="heart rate 0"),
    pytest.param(reading(status="unknown"), id="status not normal/low/high"),
    pytest.param(reading(customer_id=None), id="no customer id"),
    pytest.param(reading(recorded_at=None), id="no timestamp"),
    pytest.param(reading(customer_id="X" * 40), id="customer id too long"),
])
def test_database_refuses_bad_rows(db, bad):
    """Even if a bad reading got past the validator, the database rules stop it."""
    with pytest.raises(psycopg2.Error):
        save_batch(db, [bad], [])
    assert count_rows(db, "readings") == 0


def test_one_bad_row_cancels_the_whole_batch(db):
    """A batch is saved all together or not at all, so Kafka can safely resend it."""
    with pytest.raises(psycopg2.Error):
        save_batch(db, [reading(), reading(customer_id="CUST-B", heart_rate=999)], [("x", "invalid_json")])
    assert count_rows(db, "readings") == 0
    assert count_rows(db, "rejected_readings") == 0


def test_connection_still_works_after_a_failed_batch(db):
    with pytest.raises(psycopg2.Error):
        save_batch(db, [reading(heart_rate=999)], [])
    assert save_batch(db, [reading()], []) == 1   # rollback left the connection usable


def test_connect_gives_up_if_database_is_down(monkeypatch):
    def database_down(**settings):
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(database.psycopg2, "connect", database_down)
    monkeypatch.setattr(database.time, "sleep", lambda seconds: None)   # don't really wait
    with pytest.raises(SystemExit, match="Could not connect to PostgreSQL"):
        database.connect()

