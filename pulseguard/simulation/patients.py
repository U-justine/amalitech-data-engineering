# The clinic's patients, each with their own heart rate limits.
#
# 45 bpm is normal for an athlete but low for most people.
# 130 bpm is fine at 25 but high at 80.
# (The lab calls the patient id "customer_id", so we keep that name.)
import random

from pulseguard import config

# profile: (age range, resting heart rate range, low limit)
PROFILES = {
    "athlete": ((18, 40), (45, 58), 40),
    "adult":   ((25, 64), (60, 80), 50),
    "senior":  ((65, 90), (62, 82), 50),
}


# High limit = 85% of the maximum heart rate (220 - age).
def high_limit_for_age(age):
    return round(0.85 * (220 - age))


# Make a random patient, e.g. PT-0007, a 72-year-old senior.
def make_patient(number, rng=random):
    profile = rng.choices(["athlete", "adult", "senior"], weights=[2, 5, 3])[0]
    (age_min, age_max), (rest_min, rest_max), low_limit = PROFILES[profile]
    age = rng.randint(age_min, age_max)
    return {
        "customer_id": f"PT-{number:04d}",
        "profile": profile,
        "age": age,
        "resting_bpm": rng.randint(rest_min, rest_max),
        "low_limit": low_limit,
        "high_limit": high_limit_for_age(age),
    }


# Get `count` patients from the database, adding new ones if there aren't enough yet.
def load_or_create_patients(conn, count):
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM patients")
        existing = cur.fetchone()[0]
        for number in range(existing + 1, count + 1):
            p = make_patient(number)
            cur.execute(
                """INSERT INTO patients (customer_id, profile, age, resting_bpm, low_limit, high_limit)
                   VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (p["customer_id"], p["profile"], p["age"], p["resting_bpm"], p["low_limit"], p["high_limit"]),
            )
        cur.execute(
            """SELECT customer_id, profile, age, resting_bpm, low_limit, high_limit
               FROM patients ORDER BY customer_id LIMIT %s""", (count,))
        columns = [c.name for c in cur.description]
        patients = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.commit()
    if existing < count:
        print(f"Registered {count - existing} new patients (total {count}).")
    return patients


# Every patient's limits: {customer_id: (low, high)}.
def load_limits(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT customer_id, low_limit, high_limit FROM patients")
        limits = {customer_id: (low, high) for customer_id, low, high in cur.fetchall()}
    conn.commit()
    return limits


# One patient's (low, high), or the default limits if we don't know them.
def limits_for(limits, customer_id):
    return limits.get(customer_id, (config.NORMAL_MIN, config.NORMAL_MAX))
