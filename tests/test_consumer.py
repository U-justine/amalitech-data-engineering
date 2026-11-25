# Tests the consumer with a fake Kafka. The database tests need PostgreSQL:
#   PowerShell:  $env:TEST_DB="host=localhost port=5433 dbname=heartbeat_test user=heartbeat password=heartbeat"
import json

import pytest
from kafka.errors import NoBrokersAvailable

from pulseguard.services import consumer
from conftest import FakeKafkaConsumer
from pulseguard.processing.timing import new_timing, timing_text
from pulseguard.processing.readings import sort_messages
from pulseguard.processing.batch import process_one_batch


def msg(customer, second, heart_rate):
    timestamp = f"2026-01-01T12:00:{second:02d}+00:00"
    return json.dumps({"customer_id": customer, "timestamp": timestamp, "heart_rate": heart_rate}).encode()


def new_totals():
    return {"received": 0, "saved": 0, "low_or_high": 0, "rejected": 0, "duplicates": 0}


def run_until_empty(kafka, db):
    totals = new_totals()
    while process_one_batch(kafka, db, totals, quiet=True):
        pass
    return totals


def count_rows(db, table):
    with db.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")
        return cur.fetchone()[0]


class BrokenDatabase:
    """Pretends the database has gone down."""
    def cursor(self):
        raise RuntimeError("database is down")

    def rollback(self):
        pass


# ---------------------------------------------------------------- good cases

def test_sort_messages():
    good, rejected = sort_messages([msg("A", 0, 70), msg("A", 1, 40), b"{oops", msg("A", 2, 999)], quiet=True)
    assert [r["status"] for r in good] == ["normal", "low"]
    assert [problem for _, problem in rejected] == ["invalid_json", "impossible_heart_rate"]


def test_full_flow_into_database(db):
    messages = [
        msg("CUST-A", 0, 72),    # normal
        msg("CUST-A", 1, 45),    # low
        msg("CUST-B", 0, 150),   # high
        msg("CUST-B", 1, 0),     # rejected
        b"garbage",              # rejected
        msg("CUST-A", 0, 72),    # same as the first one -> duplicate, skipped
    ]
    kafka = FakeKafkaConsumer(messages, batch_size=4)
    totals = run_until_empty(kafka, db)

    assert totals == {"received": 6, "saved": 3, "low_or_high": 2, "rejected": 2, "duplicates": 1, "alerts": 0}
    assert kafka.commits == 2   # two batches, each committed after saving

    with db.cursor() as cur:
        cur.execute("SELECT customer_id, heart_rate, status FROM readings ORDER BY id")
        assert cur.fetchall() == [("CUST-A", 72, "normal"), ("CUST-A", 45, "low"), ("CUST-B", 150, "high")]
        cur.execute("SELECT reason FROM rejected_readings ORDER BY id")
        assert [row[0] for row in cur.fetchall()] == ["impossible_heart_rate", "invalid_json"]
        cur.execute("SELECT customer_id, heart_rate FROM latest_readings")
        assert cur.fetchall() == [("CUST-A", 45), ("CUST-B", 150)]
        # every saved reading has its timing filled in
        cur.execute("SELECT count(*) FROM readings WHERE sent_at IS NULL OR received_at IS NULL "
                    "OR kafka_seconds IS NULL OR save_seconds IS NULL OR total_seconds IS NULL")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT min(kafka_seconds), max(total_seconds) FROM readings")
        fastest_kafka, slowest_total = cur.fetchone()
        assert fastest_kafka >= 0.04 and slowest_total < 5   # fake messages were sent 50 ms earlier


def test_timing_is_measured(db):
    """The consumer measures producer -> consumer delay and saving time."""
    timing = new_timing()
    process_one_batch(FakeKafkaConsumer([msg("CUST-A", 0, 70), msg("CUST-A", 1, 71)]), db,
                      new_totals(), quiet=True, timings=[timing])
    assert timing["batches"] == 1 and timing["messages"] == 2
    assert 50 <= timing["delay_ms"] / 2 < 1000     # fake messages were "sent" 50 ms earlier
    assert timing["save_ms"] > 0
    assert "producer -> consumer: avg" in timing_text(timing)


def test_timing_text_with_no_messages():
    assert timing_text(new_timing()) == "no new messages"


# ---------------------------------------------------------------- error cases

def test_empty_poll_does_nothing():
    """No new messages: nothing is saved and nothing is committed."""
    kafka = FakeKafkaConsumer([])
    assert process_one_batch(kafka, BrokenDatabase(), new_totals(), quiet=True) == 0
    assert kafka.commits == 0


def test_batch_of_only_bad_messages(db):
    """Every message is bad: nothing goes into readings, all go to rejected_readings."""
    kafka = FakeKafkaConsumer([b"", b"not json", msg("CUST-A", 0, 0), msg("CUST-A", 1, 999)])
    totals = run_until_empty(kafka, db)
    assert totals["saved"] == 0 and totals["rejected"] == 4
    assert count_rows(db, "readings") == 0
    assert count_rows(db, "rejected_readings") == 4
    assert kafka.commits == 1   # bad messages are still "done", so they are not read again


def test_reading_the_same_messages_twice_saves_them_once(db):
    """Like a crash before commit: Kafka sends the same messages again."""
    messages = [msg(f"CUST-{c}", s, 70) for c in range(5) for s in range(3)]
    first = run_until_empty(FakeKafkaConsumer(messages), db)
    second = run_until_empty(FakeKafkaConsumer(messages), db)
    assert first["saved"] == 15
    assert second["saved"] == 0 and second["duplicates"] == 15
    assert count_rows(db, "readings") == 15


def test_nothing_is_committed_if_the_database_fails():
    kafka = FakeKafkaConsumer([msg("CUST-A", 0, 70)])
    with pytest.raises(RuntimeError):
        process_one_batch(kafka, BrokenDatabase(), new_totals(), quiet=True)
    assert kafka.commits == 0


def test_database_fails_then_recovers(db):
    """The database is down for the first try. Because nothing was committed,
    Kafka sends the same messages again, and this time they are saved."""
    messages = [msg("CUST-A", 0, 70), msg("CUST-A", 1, 140)]

    first_try = FakeKafkaConsumer(messages)
    with pytest.raises(RuntimeError):
        process_one_batch(first_try, BrokenDatabase(), new_totals(), quiet=True)
    assert first_try.commits == 0

    second_try = FakeKafkaConsumer(messages)   # Kafka re-delivers the uncommitted messages
    totals = run_until_empty(second_try, db)
    assert totals["saved"] == 2
    assert second_try.commits == 1
    assert count_rows(db, "readings") == 2


def test_consumer_gives_up_if_kafka_is_down(monkeypatch):
    def kafka_down(*args, **kwargs):
        raise NoBrokersAvailable()

    monkeypatch.setattr(consumer, "KafkaConsumer", kafka_down)
    monkeypatch.setattr(consumer.time, "sleep", lambda seconds: None)   # don't really wait
    with pytest.raises(SystemExit, match="Could not connect to Kafka"):
        consumer.connect_to_kafka()
