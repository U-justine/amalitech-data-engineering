# Tests for patients.py: each patient gets their own heart rate limits.
import random

import pytest

from pulseguard.simulation.patients import high_limit_for_age, limits_for, load_limits, load_or_create_patients, make_patient


@pytest.mark.parametrize("age, high", [
    pytest.param(20, 170, id="20 years old"),
    pytest.param(40, 153, id="40 years old"),
    pytest.param(80, 119, id="80 years old"),
])
def test_high_limit_depends_on_age(age, high):
    assert high_limit_for_age(age) == high


def test_profiles_have_sensible_limits():
    random.seed(1)
    for number in range(1, 200):
        p = make_patient(number)
        assert p["customer_id"] == f"PT-{number:04d}"
        assert p["low_limit"] < p["resting_bpm"] < p["high_limit"]
        if p["profile"] == "athlete":
            assert p["low_limit"] == 40 and p["resting_bpm"] <= 58
        if p["profile"] == "senior":
            assert p["age"] >= 65


def test_same_heart_rate_means_different_things_for_different_patients():
    limits = {"PT-ATHLETE": (40, 165), "PT-SENIOR": (50, 119)}
    assert limits_for(limits, "PT-ATHLETE") == (40, 165)
    from pulseguard.processing.validator import get_status
    assert get_status(45, *limits_for(limits, "PT-ATHLETE")) == "normal"   # fit athlete
    assert get_status(45, *limits_for(limits, "PT-SENIOR")) == "low"
    assert get_status(130, *limits_for(limits, "PT-ATHLETE")) == "normal"
    assert get_status(130, *limits_for(limits, "PT-SENIOR")) == "high"


def test_unregistered_patient_gets_clinic_defaults():
    assert limits_for({}, "PT-9999") == (50, 120)


def test_patients_are_registered_once(db):
    first = load_or_create_patients(db, 5)
    again = load_or_create_patients(db, 5)
    more = load_or_create_patients(db, 8)
    assert [p["customer_id"] for p in first] == ["PT-0001", "PT-0002", "PT-0003", "PT-0004", "PT-0005"]
    assert first == again                        # the same people, not new random ones
    assert len(more) == 8 and more[:5] == first
    assert len(load_limits(db)) == 8


# ---------------------------------------------------------------- error cases

@pytest.mark.parametrize("profile, age, low, high", [
    pytest.param("child", 30, 50, 150, id="unknown profile"),
    pytest.param("adult", 150, 50, 150, id="age 150"),
    pytest.param("adult", 30, 120, 100, id="low limit above high limit"),
])
def test_database_refuses_bad_patients(db, profile, age, low, high):
    import psycopg2
    with pytest.raises(psycopg2.Error):
        with db.cursor() as cur:
            cur.execute("""INSERT INTO patients (customer_id, profile, age, resting_bpm, low_limit, high_limit)
                           VALUES ('PT-BAD', %s, %s, 70, %s, %s)""", (profile, age, low, high))
    db.rollback()
