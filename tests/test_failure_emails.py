# When a part of PulseGuard fails, the IT team actually gets an email (real local email server).

from kafka.errors import NoBrokersAvailable
import psycopg2
import pytest

from helpers import consumer_without_patients, no_waiting
from pulseguard.services import consumer, producer
from pulseguard.storage import database
from scripts import check_pipeline


# Error cases

def test_email_when_consumer_cannot_reach_the_database(mail_server, monkeypatch):
    def database_down(**settings):
        raise psycopg2.OperationalError("connection refused")

    no_waiting(monkeypatch)
    monkeypatch.setattr(database.psycopg2, "connect", database_down)
    monkeypatch.setattr("sys.argv", ["consumer.py"])

    with pytest.raises(SystemExit):
        consumer.main()

    assert len(mail_server) == 1
    assert mail_server[0]["subject"] == "[PulseGuard] SYSTEM PROBLEM: heart rates are not being checked (database not reachable)"


def test_email_when_consumer_cannot_reach_kafka(mail_server, monkeypatch):
    class Connection:
        def close(self):
            pass

    def kafka_down(*args, **kwargs):
        raise NoBrokersAvailable()

    no_waiting(monkeypatch)
    consumer_without_patients(monkeypatch)
    monkeypatch.setattr(consumer, "connect", lambda: Connection())
    monkeypatch.setattr(consumer, "KafkaConsumer", kafka_down)
    monkeypatch.setattr("sys.argv", ["consumer.py"])

    with pytest.raises(SystemExit):
        consumer.main()

    assert len(mail_server) == 1
    assert mail_server[0]["subject"] == "[PulseGuard] SYSTEM PROBLEM: heart rates are not being checked (Kafka not reachable)"


def test_email_when_producer_cannot_reach_kafka(mail_server, monkeypatch):
    def kafka_down(**settings):
        raise NoBrokersAvailable()

    class Connection:
        def close(self): pass

    no_waiting(monkeypatch)
    monkeypatch.setattr(producer, "connect", lambda: Connection())
    monkeypatch.setattr(producer, "load_or_create_patients", lambda conn, count: [])
    monkeypatch.setattr(producer, "KafkaProducer", kafka_down)
    monkeypatch.setattr("sys.argv", ["producer.py"])

    with pytest.raises(SystemExit):
        producer.main()

    assert len(mail_server) == 1
    assert mail_server[0]["subject"] == "[PulseGuard] SYSTEM PROBLEM: no new heart rates are arriving (Kafka not reachable)"


def test_email_when_pipeline_check_fails(mail_server, monkeypatch):
    """Nothing reaches the database (e.g. the consumer is stopped): every check
    fails, and the email lists which checks failed."""
    class FakeProducer:
        def __init__(self, **settings): pass
        def send(self, topic, value, key=None): pass
        def flush(self): pass
        def close(self): pass

    class EmptyDatabase:
        autocommit = False
        def cursor(self): return self
        def __enter__(self): return self
        def __exit__(self, *error): pass
        def execute(self, sql, params=None): pass
        def fetchall(self): return []
        def fetchone(self): return (0,)
        def commit(self): pass
        def close(self): pass

    monkeypatch.setattr(check_pipeline, "KafkaProducer", FakeProducer)
    monkeypatch.setattr(check_pipeline.psycopg2, "connect", lambda **settings: EmptyDatabase())
    monkeypatch.setattr(check_pipeline.time, "sleep", lambda seconds: None)

    assert check_pipeline.main() == 1

    assert len(mail_server) == 1
    email = mail_server[0]
    # only the "20 s spike -> no alert" check passes, because nothing at all was saved
    assert email["subject"] == (f"[PulseGuard] SYSTEM PROBLEM: self-check failed "
                                f"(only 1 of {len(check_pipeline.TESTS)} checks passed)")
    plain, technical = email["body"].split("Technical details (for the IT team)")
    # the top says, in plain words, which areas are broken and the likely reason
    assert "Saving heart rate readings ............. NOT WORKING (0 of 6 checks passed)" in plain
    assert "the consumer is probably not running, or the database is down" in plain
    assert "No, readings wait safely in Kafka." in plain
    assert "resting heart rate" not in plain                  # the test-by-test list is only ...
    assert "resting heart rate: expected normal, got not saved" in technical   # ... for the IT team
    assert "resting heart rate: expected normal, got not saved" in email["body"]
    assert "broken JSON: expected rejected:invalid_json, got not rejected" in email["body"]
