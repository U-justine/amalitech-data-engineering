# Tests for validator.py: good readings, and every way a message can be wrong.
import json
from datetime import datetime, timedelta, timezone

import pytest

from pulseguard.processing.validator import check_reading

NOW = datetime.now(timezone.utc).isoformat()


# A good message, with some fields changed or removed (use None to remove).
def message(**changes):
    data = {"customer_id": "CUST-001", "timestamp": NOW, "heart_rate": 72}
    data.update(changes)
    data = {key: value for key, value in data.items() if value is not None}
    return json.dumps(data).encode()


# Good cases

@pytest.mark.parametrize("heart_rate, status", [
    pytest.param(72, "normal", id="resting"),
    pytest.param(50, "normal", id="lowest normal (50)"),
    pytest.param(120, "normal", id="highest normal (120)"),
    pytest.param(49, "low", id="just below normal (49)"),
    pytest.param(25, "low", id="lowest possible (25)"),
    pytest.param(121, "high", id="just above normal (121)"),
    pytest.param(230, "high", id="highest possible (230)"),
])
def test_status(heart_rate, status):
    reading, problem = check_reading(message(heart_rate=heart_rate))
    assert problem is None
    assert reading["status"] == status


def test_good_message():
    reading, problem = check_reading(message())
    assert problem is None
    assert reading["customer_id"] == "CUST-001"
    assert reading["heart_rate"] == 72


def test_decimal_heart_rate_is_rounded():
    reading, _ = check_reading(message(heart_rate=72.6))
    assert reading["heart_rate"] == 73


def test_timestamp_ending_in_z_is_accepted():
    reading, problem = check_reading(message(timestamp="2026-01-01T12:00:00Z"))
    assert problem is None


def test_timestamp_without_time_zone_is_treated_as_utc():
    reading, problem = check_reading(message(timestamp="2026-01-01T12:00:00"))
    assert problem is None
    assert reading["recorded_at"].tzinfo == timezone.utc


# Error cases

@pytest.mark.parametrize("raw, problem", [
    # Broken or empty messages
    pytest.param(b"this is not json", "invalid_json", id="not JSON"),
    pytest.param(b"", "invalid_json", id="empty message"),
    pytest.param(b"   ", "invalid_json", id="only spaces"),
    pytest.param(b"\xff\xfe\x00", "invalid_json", id="unreadable bytes"),
    pytest.param(b'{"customer_id": "CUST-001"', "invalid_json", id="cut-off JSON"),
    pytest.param(b"[1, 2, 3]", "invalid_json", id="JSON list instead of object"),
    pytest.param(b"null", "invalid_json", id="JSON null"),
    pytest.param(b"72", "invalid_json", id="just a number"),
    # Missing fields
    pytest.param(message(heart_rate=None), "missing_heart_rate", id="no heart_rate"),
    pytest.param(message(customer_id=None), "missing_customer_id", id="no customer_id"),
    pytest.param(message(timestamp=None), "missing_timestamp", id="no timestamp"),
    pytest.param(b"{}", "missing_customer_id", id="empty object"),
    pytest.param(b'{"customer_id": null, "timestamp": "x", "heart_rate": 70}', "missing_customer_id", id="customer_id is null"),
    # Bad customer id
    pytest.param(message(customer_id=123), "invalid_customer_id", id="customer_id is a number"),
    pytest.param(message(customer_id=""), "invalid_customer_id", id="customer_id is empty"),
    pytest.param(message(customer_id="X" * 33), "invalid_customer_id", id="customer_id too long"),
    # Bad timestamp
    pytest.param(message(timestamp="yesterday"), "invalid_timestamp", id="timestamp is a word"),
    pytest.param(message(timestamp="2026-13-45T99:00:00"), "invalid_timestamp", id="impossible date"),
    pytest.param(message(timestamp=1700000000), "invalid_timestamp", id="timestamp is a number"),
    pytest.param(message(timestamp=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()),
                 "future_timestamp", id="timestamp 1 hour in future"),
    # Bad heart rate
    pytest.param(message(heart_rate="72"), "heart_rate_not_a_number", id="heart_rate is text"),
    pytest.param(message(heart_rate=True), "heart_rate_not_a_number", id="heart_rate is true/false"),
    pytest.param(message(heart_rate=[72]), "heart_rate_not_a_number", id="heart_rate is a list"),
    pytest.param(b'{"customer_id": "C1", "timestamp": "2026-01-01T00:00:00Z", "heart_rate": NaN}',
                 "heart_rate_not_a_number", id="heart_rate is NaN"),
    pytest.param(message(heart_rate=0), "impossible_heart_rate", id="heart_rate 0"),
    pytest.param(message(heart_rate=-5), "impossible_heart_rate", id="heart_rate negative"),
    pytest.param(message(heart_rate=24), "impossible_heart_rate", id="just below possible (24)"),
    pytest.param(message(heart_rate=231), "impossible_heart_rate", id="just above possible (231)"),
    pytest.param(message(heart_rate=230.6), "impossible_heart_rate", id="230.6 rounds to 231"),
    pytest.param(message(heart_rate=300), "impossible_heart_rate", id="heart_rate 300"),
])
def test_bad_messages_are_rejected(raw, problem):
    reading, found_problem = check_reading(raw)
    assert reading is None
    assert found_problem == problem
