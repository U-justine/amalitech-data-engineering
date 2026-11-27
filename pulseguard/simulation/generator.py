# Makes fake heart rate readings, like a smartwatch.
#
# Three things can happen:
#   1. Normal life: the rate drifts around the resting rate, sometimes exercise.
#   2. Medical event (rare): the rate goes out of range and stays there -> alert.
#   3. Sensor glitch: one bad value (0, 300, or a short spike) -> no alert.
#
# Try it:   python -m pulseguard.simulation.generator
import random
from datetime import datetime, timezone

from pulseguard.simulation.patients import make_patient


def start_watching(patient):
    """Add the fields the simulation needs."""
    patient["current"] = patient["resting_bpm"]   # heart rate now
    patient["exercise_left"] = 0                   # seconds of exercise left
    patient["exercise_target"] = patient["resting_bpm"]
    patient["event_left"] = 0                      # seconds of medical event left
    patient["event_target"] = patient["resting_bpm"]
    return patient


def start_medical_event(patient, kind="high", seconds=60, serious=False):
    """Send the heart rate out of range and keep it there.
    serious=True: far enough out to be CRITICAL (used by --emergency, so the demo always emails)."""
    patient["event_left"] = seconds
    if kind == "high":
        extra = random.randint(22, 32) if serious else random.randint(12, 30)
        patient["event_target"] = patient["high_limit"] + extra
    else:
        below = random.randint(12, 16) if serious else random.randint(6, 12)
        patient["event_target"] = max(30, patient["low_limit"] - below)


def next_heart_rate(patient, event_chance=0.0):
    """The next heart rate (one per second)."""
    # 1. Maybe start a (rare) medical event
    if patient["event_left"] == 0 and random.random() < event_chance:
        start_medical_event(patient, random.choice(["high", "low"]), random.randint(45, 90))
    # 2. Maybe start exercising (3% chance), staying inside the limits
    if patient["exercise_left"] == 0 and random.random() < 0.03:
        patient["exercise_left"] = random.randint(10, 40)
        room = patient["high_limit"] - patient["resting_bpm"]       # space below the high limit
        patient["exercise_target"] = patient["resting_bpm"] + round(room * random.uniform(0.3, 0.6))

    # 3. Where is the heart rate heading?
    if patient["event_left"] > 0:
        target = patient["event_target"]
        patient["event_left"] -= 1
    elif patient["exercise_left"] > 0:
        target = patient["exercise_target"]
        patient["exercise_left"] -= 1
    else:
        target = patient["resting_bpm"]

    # 4. Move a quarter of the way there, plus a little noise
    patient["current"] += (target - patient["current"]) * 0.25 + random.uniform(-3, 3)
    return round(patient["current"])


def glitch(patient):
    """One bad value from the sensor."""
    return random.choice([
        0,                                                      # impossible -> rejected
        random.randint(260, 320),                               # impossible -> rejected
        patient["high_limit"] + random.randint(10, 40),         # short spike -> no alert
        max(30, patient["low_limit"] - random.randint(5, 15)),  # short dip -> no alert
    ])


def make_reading(patient, bad_chance=0.02, event_chance=0.0):
    """One reading. bad_chance = how often a glitch happens (0.02 = 2%)."""
    heart_rate = next_heart_rate(patient, event_chance)
    if random.random() < bad_chance:
        heart_rate = glitch(patient)

    return {
        "customer_id": patient["customer_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "heart_rate": heart_rate,
    }


if __name__ == "__main__":
    for number in range(1, 4):
        patient = start_watching(make_patient(number))
        print(patient["profile"], patient["age"], "limits", patient["low_limit"], "-", patient["high_limit"],
              make_reading(patient))


def start_emergencies(patients, patient_ids, kind):
    """--emergency PT-0007: make these patients' heart rate go high (or low) for 75 seconds."""
    for patient_id in patient_ids:
        patient = next((p for p in patients if p["customer_id"] == patient_id), None)
        if patient is None:
            raise SystemExit(f"--emergency: no patient called {patient_id}")
        start_medical_event(patient, kind, seconds=75, serious=True)
        print(f"EMERGENCY: {patient_id} ({patient['profile']}, age {patient['age']}, "
              f"limits {patient['low_limit']}-{patient['high_limit']} bpm) heart rate will go "
              f"{kind} for 75 seconds")
