# Tests for producer.py and generator.py error handling (no real Kafka needed).
import json

import pytest
from kafka.errors import NoBrokersAvailable

from pulseguard.services import producer
from pulseguard.simulation.generator import make_reading, start_watching
from pulseguard.simulation.patients import make_patient


class FakeKafkaProducer:
    """Pretends to be Kafka and remembers what was sent."""
    last = None   # the most recently created fake producer

    def __init__(self, **settings):
        self.settings = settings
        self.sent = []
        FakeKafkaProducer.last = self

    def send(self, topic, key, value):
        self.sent.append((topic, self.settings["key_serializer"](key), self.settings["value_serializer"](value)))

    def flush(self):
        pass

    def close(self):
        pass


def test_producer_sends_json_with_customer_key(monkeypatch):
    class Connection:
        def close(self): pass
    monkeypatch.setattr(producer, "connect", lambda: Connection())
    monkeypatch.setattr(producer, "load_or_create_patients",
                        lambda conn, count: [make_patient(n) for n in range(1, count + 1)])
    monkeypatch.setattr(producer, "KafkaProducer", FakeKafkaProducer)
    clock = [1000.0]   # a pretend clock, so the test doesn't really wait
    monkeypatch.setattr(producer.time, "time", lambda: clock[0])
    monkeypatch.setattr(producer.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr("sys.argv", ["producer.py", "--patients", "3", "--seconds", "2"])

    producer.main()

    sent = FakeKafkaProducer.last.sent
    assert len(sent) == 9   # 3 patients x 3 rounds (at 0, 1 and 2 seconds)
    topic, key, value = sent[0]
    assert topic == "heartbeats"
    assert key == b"PT-0001"
    assert set(json.loads(value)) == {"customer_id", "timestamp", "heart_rate"}


def test_producer_gives_up_if_kafka_is_down(monkeypatch):
    def kafka_down(**settings):
        raise NoBrokersAvailable()

    monkeypatch.setattr(producer, "KafkaProducer", kafka_down)
    monkeypatch.setattr(producer.time, "sleep", lambda seconds: None)
    with pytest.raises(SystemExit, match="Could not connect to Kafka"):
        producer.connect_to_kafka()


def test_emergency_for_unknown_patient_stops_with_a_message(monkeypatch):
    class Connection:
        def close(self): pass
    monkeypatch.setattr(producer, "connect", lambda: Connection())
    monkeypatch.setattr(producer, "load_or_create_patients",
                        lambda conn, count: [make_patient(n) for n in range(1, count + 1)])
    monkeypatch.setattr(producer, "send_failure_email", lambda *args: True)
    monkeypatch.setattr("sys.argv", ["producer.py", "--patients", "3", "--emergency", "PT-0099"])
    with pytest.raises(SystemExit, match="no patient called PT-0099"):
        producer.main()


def test_bad_chance_of_one_makes_every_reading_bad():
    patient = start_watching(make_patient(1))
    for _ in range(100):
        heart_rate = make_reading(patient, bad_chance=1.0)["heart_rate"]
        assert heart_rate < patient["low_limit"] or heart_rate > patient["high_limit"]
