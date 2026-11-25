# The 19 test messages the self-check sends, and what should happen to each.
# Test patients are called TEST-<run id>-<number>, so they never mix with real ones.
import uuid
from datetime import datetime, timedelta, timezone

RUN_ID = uuid.uuid4().hex[:6].upper()        # makes this run's patient ids unique
START = datetime.now(timezone.utc).replace(microsecond=0)


def customer(number):
    return f"TEST-{RUN_ID}-{number}"


def reading(number, second, heart_rate):
    timestamp = (START + timedelta(seconds=second)).isoformat()
    return {"customer_id": customer(number), "timestamp": timestamp, "heart_rate": heart_rate}


# (description, message, expected result)
TESTS = [
    # Good readings
    ("resting heart rate",    reading(1, 0, 68),    "normal"),
    ("exercising, still ok",  reading(1, 1, 118),   "normal"),
    ("exactly 50",            reading(2, 1, 50),    "normal"),
    ("exactly 120",           reading(2, 2, 120),   "normal"),
    ("too low",               reading(1, 2, 42),    "low"),
    ("too high",              reading(2, 0, 165),   "high"),
    # Error cases
    ("sensor says 0",         reading(3, 0, 0),     "rejected:impossible_heart_rate"),
    ("sensor says 300",       reading(3, 1, 300),   "rejected:impossible_heart_rate"),
    ("negative heart rate",   reading(3, 2, -10),   "rejected:impossible_heart_rate"),
    ("heart rate is text",    {**reading(3, 3, 0), "heart_rate": "72"},     "rejected:heart_rate_not_a_number"),
    ("missing heart rate",    {"customer_id": customer(3), "timestamp": START.isoformat()},
                                                    "rejected:missing_heart_rate"),
    ("missing customer id",   {"timestamp": START.isoformat(), "heart_rate": 70, "note": RUN_ID},
                                                    "rejected:missing_customer_id"),
    ("bad timestamp",         {**reading(3, 4, 70), "timestamp": "now"},    "rejected:invalid_timestamp"),
    ("timestamp in future",   reading(3, 7200, 70), "rejected:future_timestamp"),
    ("broken JSON",           f"{{TEST-{RUN_ID} broken",                    "rejected:invalid_json"),
    ("JSON list, not object", f'["TEST-{RUN_ID}", 72]',                     "rejected:invalid_json"),
    ("same reading twice",    reading(1, 0, 68),    "duplicate"),
    # Health alerts (test patients use the default limits 50-120)
    ("20 s spike",            "story:8",            "no alert"),
    ("35 s racing heart",     "story:9",            "alert:high:emailed"),
]

# The two heart-rate stories (one reading per second)
STORIES = {
    "story:8": [reading(8, s, 150) for s in range(20)] + [reading(8, 20, 70)],
    "story:9": [reading(9, s, 150) for s in range(35)] + [reading(9, 35, 70)],
}
