import random

from pulseguard.simulation.generator import make_reading, start_medical_event, start_watching
from pulseguard.simulation.patients import make_patient


def watched(number, **profile):
    patient = make_patient(number)
    patient.update(profile)
    return start_watching(patient)


def test_reading_has_the_three_lab_fields():
    reading = make_reading(watched(1))
    assert set(reading) == {"customer_id", "timestamp", "heart_rate"}
    assert reading["customer_id"] == "PT-0001"
    assert isinstance(reading["heart_rate"], int)


# Without glitches or medical events, nobody should trigger an alert.
def test_normal_life_stays_inside_each_patients_limits():
    random.seed(1)
    patients = [watched(n) for n in range(1, 41)]
    for _ in range(300):
        for p in patients:
            hr = make_reading(p, bad_chance=0, event_chance=0)["heart_rate"]
            assert p["low_limit"] - 8 <= hr <= p["high_limit"] + 8


def test_heart_rate_changes_gradually():
    random.seed(2)
    patient = watched(1)
    rates = [make_reading(patient, bad_chance=0)["heart_rate"] for _ in range(300)]
    biggest_jump = max(abs(a - b) for a, b in zip(rates, rates[1:]))
    assert biggest_jump < 20


def test_medical_event_goes_above_high_limit_and_stays():
    random.seed(3)
    patient = watched(1, high_limit=130, resting_bpm=70)
    start_watching(patient)
    start_medical_event(patient, "high", seconds=60)
    rates = [make_reading(patient, bad_chance=0)["heart_rate"] for _ in range(60)]
    assert all(r > 130 for r in rates[15:58])     # after ~15 s it stays above the limit


def test_medical_event_low():
    random.seed(4)
    patient = watched(1, low_limit=50, resting_bpm=70)
    start_watching(patient)
    start_medical_event(patient, "low", seconds=60)
    rates = [make_reading(patient, bad_chance=0)["heart_rate"] for _ in range(60)]
    assert all(r < 50 for r in rates[15:58])


def test_glitches_happen_at_the_bad_chance_rate():
    random.seed(5)
    patients = [watched(n) for n in range(1, 11)]
    readings = [(p, make_reading(p, bad_chance=0.2)["heart_rate"]) for _ in range(300) for p in patients]
    glitches = sum(1 for p, hr in readings if hr < p["low_limit"] - 4 or hr > p["high_limit"] + 4)
    assert 0.12 < glitches / len(readings) < 0.28


# --emergency must always give a CRITICAL alert (the only kind emailed by default).
def test_demo_emergency_is_always_critical():
    from pulseguard.simulation.generator import start_emergencies
    for seed in range(50):
        random.seed(seed)
        high = [start_watching(watched(1, high_limit=130, resting_bpm=70))]
        start_emergencies(high, ["PT-0001"], "high")
        assert high[0]["event_target"] >= 130 + 20            # 20+ above the limit = critical
        low = [start_watching(watched(1, low_limit=50, resting_bpm=70))]
        start_emergencies(low, ["PT-0001"], "low")
        assert low[0]["event_target"] <= 50 - 10              # 10+ below the limit = critical
