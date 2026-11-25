# Tests for episodes.py: when does a patient get a health alert?
from datetime import datetime, timedelta, timezone

from pulseguard.processing.episodes import update_episodes

START = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
LOW, HIGH = 50, 130   # this patient's limits


def feed(state, heart_rates, patient="PT-0001", start_second=0, keep_updates=False):
    """Feed one reading per second. Returns the opened/closed events
    (and the "updated" ones too if keep_updates=True)."""
    events = []
    for i, hr in enumerate(heart_rates):
        reading = {"customer_id": patient, "recorded_at": START + timedelta(seconds=start_second + i),
                   "heart_rate": hr}
        events += update_episodes(state, reading, LOW, HIGH)
    return [(event, e) for event, e in events if keep_updates or event != "updated"]


# ---------------------------------------------------------------- good cases

def test_normal_readings_never_alert():
    assert feed({}, [70] * 300) == []


def test_alert_opens_after_30_seconds_out_of_range():
    state = {}
    assert feed(state, [140] * 30) == []                 # 0..29 s: not yet
    events = feed(state, [140], start_second=30)         # 30 s: alert
    assert [event for event, _ in events] == ["opened"]
    episode = events[0][1]
    assert episode["kind"] == "high" and episode["limit_bpm"] == HIGH
    assert episode["started_at"] == START                # counted from the first high reading
    assert episode["severity"] == "warning"


def test_alert_opens_only_once_then_closes_when_normal():
    events = feed({}, [140] * 90 + [80])
    assert [event for event, _ in events] == ["opened", "closed"]
    closed = events[1][1]
    assert closed["ended_at"] == START + timedelta(seconds=90)
    assert closed["reading_count"] == 90


def test_critical_when_far_above_the_limit():
    events = feed({}, [135] * 31 + [155] * 5 + [80])
    assert events[0][1]["severity"] == "warning"         # 135 is only 5 above
    assert events[1][1]["severity"] == "critical"         # it got worse: 155 >= 130 + 20
    assert events[1][1]["peak_bpm"] == 155


def test_low_episode():
    events = feed({}, [45] * 31 + [60])
    assert [(event, e["kind"]) for event, e in events] == [("opened", "low"), ("closed", "low")]
    assert events[0][1]["peak_bpm"] == 45


def test_patients_are_tracked_separately():
    state = {}
    feed(state, [140] * 20, patient="PT-A")
    events = feed(state, [140] * 11, patient="PT-B", start_second=20)
    assert events == []                                  # PT-B has only been high for 11 s
    events = feed(state, [140] * 12, patient="PT-A", start_second=20)
    assert [(event, e["customer_id"]) for event, e in events] == [("opened", "PT-A")]


def test_ongoing_alert_reports_its_latest_peak():
    events = feed({}, [140] * 31 + [160, 150], keep_updates=True)
    updates = [e for event, e in events if event == "updated"]
    assert [u["peak_bpm"] for u in updates] == [160, 160]
    assert updates[-1]["reading_count"] == 33


def test_episode_id_is_the_same_if_readings_are_replayed():
    first = feed({}, [140] * 31)[0][1]["episode_id"]
    replay = feed({}, [140] * 31)[0][1]["episode_id"]
    assert first == replay == "PT-0001@2026-01-01T12:00:00+00:00"


# ---------------------------------------------------------------- error cases

def test_short_spike_is_not_an_alert():
    """A single glitch or a 20-second spike should not wake anyone up."""
    assert feed({}, [70, 200, 70]) == []
    assert feed({}, [70] + [150] * 20 + [70] * 10) == []


def test_spike_that_dips_back_to_normal_restarts_the_count():
    assert feed({}, [140] * 25 + [80] + [140] * 25) == []


def test_switching_from_high_to_low_closes_and_starts_again():
    events = feed({}, [140] * 31 + [40] * 31)
    assert [(event, e["kind"]) for event, e in events] == [("opened", "high"), ("closed", "high"), ("opened", "low")]


def test_readings_with_gaps_still_count_by_time():
    """If some readings were lost, the 30 seconds are measured by timestamps, not by counting."""
    state = {}
    feed(state, [140], start_second=0)
    events = feed(state, [140], start_second=35)
    assert [event for event, _ in events] == ["opened"]
