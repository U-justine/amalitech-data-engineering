# Checks one message before it goes into the database.
#
# check_reading() returns (reading, problem):
#   good message -> (reading, None)
#   bad message  -> (None, "what was wrong")
import json
from datetime import datetime, timedelta, timezone

from pulseguard.config import NORMAL_MAX, NORMAL_MIN, POSSIBLE_MAX, POSSIBLE_MIN


# normal, low or high (using the patient's own limits).
def get_status(heart_rate, low_limit=NORMAL_MIN, high_limit=NORMAL_MAX):
    if heart_rate < low_limit:
        return "low"
    if heart_rate > high_limit:
        return "high"
    return "normal"


# Runs the 5 checks below in order and stops at the first problem.
def check_reading(message):
    # 1. Is it valid JSON, like {"key": value}?
    try:
        data = json.loads(message)
    except (ValueError, TypeError):
        return None, "invalid_json"
    if not isinstance(data, dict):
        return None, "invalid_json"

    # 2. Are all three fields there?
    for field in ("customer_id", "timestamp", "heart_rate"):
        if data.get(field) is None:
            return None, f"missing_{field}"

    # 3. Is the patient id short text?
    customer_id = data["customer_id"]
    if not isinstance(customer_id, str) or not 1 <= len(customer_id) <= 32:
        return None, "invalid_customer_id"

    # 4. Is the timestamp a real time, not in the future?
    try:
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None, "invalid_timestamp"
    if timestamp.tzinfo is None:                       # no time zone -> UTC
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    if timestamp > datetime.now(timezone.utc) + timedelta(minutes=5):
        return None, "future_timestamp"

    # 5. Is the heart rate a number a real heart could have?
    heart_rate = data["heart_rate"]
    if isinstance(heart_rate, bool) or not isinstance(heart_rate, (int, float)):
        return None, "heart_rate_not_a_number"
    if heart_rate != heart_rate:                       # true only for NaN
        return None, "heart_rate_not_a_number"
    heart_rate = round(heart_rate)
    if heart_rate < POSSIBLE_MIN or heart_rate > POSSIBLE_MAX:
        return None, "impossible_heart_rate"

    reading = {
        "customer_id": customer_id,
        "recorded_at": timestamp,
        "heart_rate": heart_rate,
        "status": get_status(heart_rate),
    }
    return reading, None
