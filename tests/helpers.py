# Small helpers shared by the test files.
import json
from datetime import datetime, timedelta, timezone

from conftest import FakeKafkaConsumer
from pulseguard.processing.batch import new_state, process_one_batch
from pulseguard.services import consumer, producer
from pulseguard.storage import database

START = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


# One Kafka message: a patient's reading, `second` seconds after START.
def msg(patient, second, heart_rate):
    timestamp = (START + timedelta(seconds=second)).isoformat()
    return json.dumps({"customer_id": patient, "timestamp": timestamp, "heart_rate": heart_rate}).encode()


def new_totals():
    return {"received": 0, "saved": 0, "low_or_high": 0, "rejected": 0, "duplicates": 0, "alerts": 0}


# Remembers what would have been sent to the heartbeat-alerts topic.
class FakeAlertPublisher:
    def __init__(self):
        self.sent = []

    def send(self, topic, key=None, value=None):
        self.sent.append((topic, key, value))

    def flush(self):
        pass

    def close(self):
        pass


# Run the consumer's batches until Kafka (fake) is empty.
def run_consumer(db, messages, limits, publisher=None, state=None):
    state = state or new_state(limits)
    kafka = FakeKafkaConsumer(messages, batch_size=10)
    totals = new_totals()
    while process_one_batch(kafka, db, totals, quiet=True, state=state, alert_publisher=publisher):
        pass
    return totals, state


def rows(db, sql):
    with db.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


# The consumer loads patient limits and open alerts at start-up: give it none.
def consumer_without_patients(monkeypatch):
    monkeypatch.setattr(consumer, "load_limits", lambda conn: {})
    monkeypatch.setattr(consumer, "load_open_episodes", lambda conn: {})
    monkeypatch.setattr(consumer, "connect_alert_publisher", lambda: FakeAlertPublisher())


# Skip the 'try again in a few seconds' waits so the tests run fast.
def no_waiting(monkeypatch):
    monkeypatch.setattr(database.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(consumer.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(producer.time, "sleep", lambda seconds: None)
