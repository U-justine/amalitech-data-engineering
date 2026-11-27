# Health alerts in the consumer: personal limits, the 30 s rule, restarts and replays.
# Uses a real PostgreSQL test database.

from datetime import timedelta

from helpers import FakeAlertPublisher, START, msg, rows, run_consumer
from pulseguard.processing.batch import new_state
from pulseguard.storage.alerts_db import load_open_episodes


# Good cases

def test_personal_limits_decide_the_status(db):
    limits = {"PT-ATHLETE": (40, 165), "PT-SENIOR": (50, 119)}
    run_consumer(db, [msg("PT-ATHLETE", 0, 45), msg("PT-SENIOR", 0, 45),
                      msg("PT-ATHLETE", 1, 130), msg("PT-SENIOR", 1, 130)], limits)
    assert rows(db, "SELECT customer_id, heart_rate, status FROM readings ORDER BY customer_id, recorded_at") == [
        ("PT-ATHLETE", 45, "normal"), ("PT-ATHLETE", 130, "normal"),
        ("PT-SENIOR", 45, "low"), ("PT-SENIOR", 130, "high")]


def test_sustained_high_heart_rate_creates_one_alert(db):
    publisher = FakeAlertPublisher()
    messages = [msg("PT-0007", s, 70) for s in range(5)] + \
               [msg("PT-0007", s, 150) for s in range(5, 60)] + \
               [msg("PT-0007", 60, 72)]
    totals, _ = run_consumer(db, messages, {"PT-0007": (50, 130)}, publisher)

    assert totals["alerts"] == 1
    episode = rows(db, "SELECT customer_id, kind, severity, limit_bpm, peak_bpm, started_at, ended_at "
                       "FROM alert_episodes")
    assert episode == [("PT-0007", "high", "critical", 130, 150,
                        START + timedelta(seconds=5), START + timedelta(seconds=60))]
    # and the alert was published to the alerts topic: once when it started, once when it ended
    assert [(topic, key, value["event"]) for topic, key, value in publisher.sent] == [
        ("heartbeat-alerts", "PT-0007", "opened"), ("heartbeat-alerts", "PT-0007", "closed")]


def test_open_alert_survives_a_consumer_restart(db):
    limits = {"PT-0007": (50, 130)}
    run_consumer(db, [msg("PT-0007", s, 140) for s in range(40)], limits)   # alert open, then "crash"
    assert rows(db, "SELECT count(*) FROM open_alerts") == [(1,)]

    restarted = new_state(limits, load_open_episodes(db))                  # a new consumer starts
    run_consumer(db, [msg("PT-0007", 40, 75)], limits, state=restarted)     # back to normal
    assert rows(db, "SELECT count(*) FROM open_alerts") == [(0,)]
    assert rows(db, "SELECT count(*), max(reading_count) FROM alert_episodes") == [(1, 40)]


def test_replayed_readings_do_not_create_a_second_alert(db):
    limits = {"PT-0007": (50, 130)}
    messages = [msg("PT-0007", s, 140) for s in range(40)]
    run_consumer(db, messages, limits)
    run_consumer(db, messages, limits)                       # Kafka re-delivers everything
    assert rows(db, "SELECT count(*) FROM alert_episodes") == [(1,)]
