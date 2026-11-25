# When the database goes down WHILE PulseGuard is running, it must not stop.
# It keeps the batch it was holding, emails the IT team once, waits, opens a new
# connection, saves the SAME batch, emails "back online", and carries on.
# These tests use a real PostgreSQL test database and a real local email server.
import psycopg2
import pytest

from conftest import FakeKafkaConsumer
from pulseguard.services import alert_service, consumer
from pulseguard.storage import retry
from pulseguard.processing import readings
from pulseguard.storage.database import save_batch
from pulseguard.processing.episodes import new_episode
from datetime import datetime, timezone

MESSAGE = b'{"customer_id": "PT-0001", "timestamp": "2026-01-01T12:00:00+00:00", "heart_rate": 70}'
READING = {"customer_id": "PT-0001", "recorded_at": datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
           "heart_rate": 70, "status": "normal"}


class DeadConnection:
    """A connection to a database that has stopped (what psycopg2 gives you after a restart)."""
    def cursor(self):
        raise psycopg2.OperationalError("server closed the connection unexpectedly")

    def rollback(self):
        raise psycopg2.InterfaceError("connection already closed")

    def close(self):
        pass


class KeepOpen:
    """Wraps the test database so the code under test can't close it."""
    def __init__(self, conn):
        self.conn = conn

    def __getattr__(self, name):
        return getattr(self.conn, name)

    def close(self):
        pass


def count(db, table):
    with db.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")
        return cur.fetchone()[0]


def database_comes_back_after(tries, working_conn):
    """A fake reconnect(): the database is still down for `tries` attempts, then it is back."""
    attempts = []

    def fake_reconnect(old_conn):
        attempts.append(1)
        return None if len(attempts) <= tries else working_conn
    return fake_reconnect, attempts


# ---------------------------------------------------------------- good cases

def test_same_batch_is_saved_once_the_database_is_back(db, mail_server, monkeypatch):
    fake_reconnect, attempts = database_comes_back_after(2, KeepOpen(db))
    monkeypatch.setattr(retry, "reconnect", fake_reconnect)
    kafka = FakeKafkaConsumer([])

    saved, conn = retry.save_until_it_works(DeadConnection(), [READING], [], [], kafka, wait_seconds=0)

    assert saved == 1 and count(db, "readings") == 1   # the SAME reading was delivered
    assert len(attempts) == 3                          # down, down, back
    assert kafka.polls_while_paused >= 3               # told Kafka "still alive" while waiting
    assert kafka.paused is False                       # and takes new messages again afterwards
    subjects = [m["subject"] for m in mail_server]
    assert len(subjects) == 2                          # one problem email, not one per try
    assert subjects[0] == "[PulseGuard] SYSTEM PROBLEM: heart rates are not being checked (database not reachable)"
    assert subjects[1].startswith("[PulseGuard] BACK ONLINE: heart rates are being checked again")
    assert "retries every 0 s" in mail_server[0]["body"]


def test_consumer_keeps_running_through_a_database_outage(db, mail_server, monkeypatch):
    """The real consumer.main(): the database dies, comes back, and the batch is
    saved and only then committed to Kafka. No restart needed."""
    class StopAfterFirstCommit(FakeKafkaConsumer):
        def poll(self, timeout_ms=0):
            if self.commits:
                raise KeyboardInterrupt          # we have seen enough: stop like Ctrl+C
            return super().poll(timeout_ms)

    kafka = StopAfterFirstCommit([MESSAGE])
    fake_reconnect, attempts = database_comes_back_after(1, KeepOpen(db))
    monkeypatch.setattr(retry, "RETRY_EVERY_SECONDS", 0)
    monkeypatch.setattr(retry, "reconnect", fake_reconnect)
    monkeypatch.setattr(consumer, "connect", lambda: DeadConnection())   # it dies right away
    monkeypatch.setattr(consumer, "connect_to_kafka", lambda: kafka)
    monkeypatch.setattr(consumer, "load_limits", lambda conn: {})
    monkeypatch.setattr(consumer, "load_open_episodes", lambda conn: {})
    monkeypatch.setattr(consumer, "connect_alert_publisher",
                        lambda: type("P", (), {"send": lambda *a, **k: None, "flush": lambda s: None,
                                               "close": lambda s: None})())
    monkeypatch.setattr("sys.argv", ["consumer.py", "--quiet"])

    consumer.main()                                   # no crash

    assert count(db, "readings") == 1
    assert kafka.commits == 1                         # committed once, after the save worked
    subjects = [m["subject"] for m in mail_server]
    assert len(subjects) == 2
    assert subjects[0].startswith("[PulseGuard] SYSTEM PROBLEM")
    assert subjects[1].startswith("[PulseGuard] BACK ONLINE")


def test_alert_service_keeps_running_through_a_database_outage(db, mail_server, monkeypatch):
    save_batch(db, [], [], [("opened", new_episode("PT-0007", "high",
                                                   datetime(2026, 1, 1, tzinfo=timezone.utc), 130, 150, 31))])
    monkeypatch.setattr(alert_service.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(alert_service, "reconnect", lambda old: KeepOpen(db))
    kafka = FakeKafkaConsumer([])
    status = {"conn": DeadConnection(), "database_down": False, "last_retry": 0}

    alert_service.one_round(kafka, status)            # round 1: database down
    assert status["database_down"] is True
    alert_service.one_round(kafka, status)            # round 2: back, waiting alert is emailed

    subjects = [m["subject"] for m in mail_server]
    assert subjects[0] == "[PulseGuard] SYSTEM PROBLEM: health alert emails are paused (database not reachable)"
    assert "PT-0007 heart rate HIGH" in subjects[1]   # the alert that waited
    assert subjects[2].startswith("[PulseGuard] BACK ONLINE: health alert emails are being sent again")
    assert status["database_down"] is False


# ---------------------------------------------------------------- error cases

def test_a_bug_is_not_retried(monkeypatch):
    """Only 'can't reach the database' is worth waiting for. A bug would fail forever,
    so it stops straight away (and the failure email is sent by main())."""
    class BuggyConnection:
        def cursor(self):
            raise ValueError("a bug")

        def rollback(self):
            pass

    kafka = FakeKafkaConsumer([])
    with pytest.raises(ValueError):
        retry.save_until_it_works(BuggyConnection(), [READING], [], [], kafka, wait_seconds=0)
    assert kafka.polls_while_paused == 0


def test_a_row_the_database_refuses_is_not_retried(db, monkeypatch):
    bad = dict(READING, heart_rate=999)               # breaks the CHECK rule in schema.sql
    with pytest.raises(psycopg2.IntegrityError):
        retry.save_until_it_works(db, [bad], [], [], FakeKafkaConsumer([]), wait_seconds=0)


def test_messages_handed_out_while_paused_are_put_back():
    """Safety net: if Kafka still gives us messages while we wait, we go back to the
    first one, so they are read again later instead of being skipped."""
    from types import SimpleNamespace

    class LeakyKafka(FakeKafkaConsumer):
        seeks = []

        def poll(self, timeout_ms=0):
            return {"partition-0": [SimpleNamespace(value=MESSAGE, offset=41), SimpleNamespace(value=MESSAGE, offset=42)]}

        def seek(self, partition, offset):
            self.seeks.append((partition, offset))

    kafka = LeakyKafka([])
    retry.wait_and_keep_kafka_happy(kafka, seconds=0)
    assert kafka.seeks == [("partition-0", 41)]


def test_patient_limits_reload_during_an_outage_does_not_crash():
    state = consumer.new_state()
    state["limits_loaded_at"] = 0                     # "time to reload"
    readings.refresh_limits_if_needed(DeadConnection(), state, [dict(READING, customer_id="PT-NEW")])
    assert state["limits"] == {}                      # kept what it had, no crash
