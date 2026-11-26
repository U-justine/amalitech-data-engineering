# Health alert emails: alert service -> real local email server.
# Uses a real PostgreSQL test database.

from datetime import timedelta
import json
from types import SimpleNamespace

import pytest

from conftest import FakeKafkaConsumer
from helpers import FakeAlertPublisher, START, msg, rows, run_consumer
from pulseguard import config
from pulseguard.notifications import alert_emailer
from pulseguard.processing.episodes import new_episode
from pulseguard.services import alert_service
from pulseguard.storage.database import save_batch


def test_alert_service_emails_once_and_then_resolved(db, mail_server):
    save_batch(db, [], [], [("opened", new_episode("PT-0007", "high", START, 130, 152, 31))])

    assert alert_emailer.send_pending_emails(db) == 1
    assert alert_emailer.send_pending_emails(db) == 0        # already emailed: not sent again
    assert len(mail_server) == 1
    assert mail_server[0]["subject"] == "[PulseGuard] WARNING: PT-0007 heart rate HIGH (152 bpm, limit 130)"
    assert "above their limit of 130 bpm" in mail_server[0]["body"]
    assert "since 01 Jan 2026" in mail_server[0]["body"]          # a readable date, no code
    assert "Traceback" not in mail_server[0]["body"]

    closed = new_episode("PT-0007", "high", START, 130, 152, 61)
    closed["ended_at"] = START + timedelta(seconds=61)
    save_batch(db, [], [], [("closed", closed)])
    assert alert_emailer.send_pending_emails(db) == 1
    assert mail_server[1]["subject"] == "[PulseGuard] RESOLVED: PT-0007 heart rate back to normal after 61 s"
    assert rows(db, "SELECT opened_email_at IS NOT NULL, closed_email_at IS NOT NULL FROM alert_episodes") == [
        (True, True)]


def test_alert_message_triggers_email_and_is_committed(db, mail_server):
    episode = new_episode("PT-0003", "low", START, 50, 41, 31)
    save_batch(db, [], [], [("opened", episode)])
    message = SimpleNamespace(value=json.dumps({"event": "opened", **episode}, default=str).encode())
    kafka = FakeKafkaConsumer([])
    kafka.poll = lambda timeout_ms=0: {"p": [message]}

    assert alert_emailer.process_alert_messages(kafka, db) == 1
    assert kafka.commits == 1
    assert len(mail_server) == 1
    assert "PT-0003 heart rate LOW (41 bpm, limit 50)" in mail_server[0]["subject"]


# ---------------------------------------------------------------- error cases

def test_short_spike_creates_no_alert_and_no_email(db, mail_server):
    publisher = FakeAlertPublisher()
    messages = [msg("PT-0007", s, 70) for s in range(10)] + [msg("PT-0007", 10, 190)] + \
               [msg("PT-0007", s, 70) for s in range(11, 20)]
    run_consumer(db, messages, {"PT-0007": (50, 130)}, publisher)
    assert rows(db, "SELECT count(*) FROM alert_episodes") == [(0,)]
    assert publisher.sent == []
    assert alert_emailer.send_pending_emails(db) == 0 and mail_server == []


def test_replayed_kafka_messages_do_not_send_a_second_email(db, mail_server):
    """Kafka may deliver the same alert message twice (at-least-once). Only one email goes out."""
    episode = new_episode("PT-0007", "high", START, 130, 150, 31)
    save_batch(db, [], [], [("opened", episode)])
    message = SimpleNamespace(value=json.dumps({"event": "opened", **episode}, default=str).encode())
    kafka = FakeKafkaConsumer([])
    kafka.poll = lambda timeout_ms=0: {"p": [message]}

    alert_emailer.process_alert_messages(kafka, db)
    alert_emailer.process_alert_messages(kafka, db)          # the same message again
    assert len(mail_server) == 1



def test_email_server_down_then_back_alert_is_not_lost(db, mail_server, monkeypatch):
    save_batch(db, [], [], [("opened", new_episode("PT-0007", "high", START, 130, 150, 31))])

    real_port = config.SMTP_PORT
    monkeypatch.setattr(config, "SMTP_PORT", 1)              # email server "down"
    assert alert_emailer.send_pending_emails(db) == 0
    assert rows(db, "SELECT opened_email_at FROM alert_episodes") == [(None,)]   # still waiting

    monkeypatch.setattr(config, "SMTP_PORT", real_port)      # email server back
    assert alert_emailer.send_pending_emails(db) == 1
    assert len(mail_server) == 1


def test_alert_service_failure_sends_failure_email(mail_server, monkeypatch):
    import psycopg2
    from pulseguard.storage import database

    def database_down(**settings):
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(database.psycopg2, "connect", database_down)
    monkeypatch.setattr(database.time, "sleep", lambda seconds: None)
    with pytest.raises(SystemExit):
        alert_service.main()
    assert mail_server[0]["subject"] == "[PulseGuard] SYSTEM PROBLEM: health alert emails are paused (database not reachable)"


# ---------------------------------------------------------------- self-check test patients

def test_test_patient_alert_goes_to_it_team_not_doctors(mail_server):
    """Self-check patients (TEST-...) are not real: no CRITICAL email to doctors."""
    from pulseguard.notifications.health_alerts import send_health_alert
    episode = new_episode("TEST-ABC123-9", "high", START, 120, 150, 31)
    send_health_alert("opened", episode)
    email = mail_server[0]
    assert email["to"] == [config.SYSTEM_ALERT_TO]
    assert email["subject"] == "[PulseGuard] [TEST] self-check alert raised (TEST-ABC123-9)"
    assert "Not a real patient" in email["body"]


def test_self_check_removes_its_test_patients(db):
    from scripts.check_report import remove_test_data
    run_consumer(db, [msg("TEST-ABC123-1", 0, 70), msg("TEST-ABC123-9", 0, 0), msg("PT-0001", 0, 70)],
                 {}, state=None)
    save_batch(db, [], [], [("opened", new_episode("TEST-ABC123-9", "high", START, 120, 150, 31))])

    remove_test_data(db, "ABC123", wait_for_resolved=False)

    assert rows(db, "SELECT customer_id FROM readings") == [("PT-0001",)]           # real patient kept
    assert rows(db, "SELECT count(*) FROM alert_episodes") == [(0,)]
    assert rows(db, "SELECT count(*) FROM rejected_readings") == [(0,)]


# ---------------------------------------------------------------- warning that gets worse, and what the email shows

def test_warning_that_becomes_critical_sends_one_more_email(db, mail_server):
    """The doctor was told WARNING; when it gets worse they must be told again, once."""
    save_batch(db, [], [], [("opened", new_episode("PT-0007", "high", START, 130, 140, 31))])
    assert alert_emailer.send_pending_emails(db) == 1                      # WARNING email
    worse = new_episode("PT-0007", "high", START, 130, 155, 40)
    worse["severity"] = "critical"
    save_batch(db, [], [], [("escalated", worse)])
    assert alert_emailer.send_pending_emails(db) == 1                      # NOW CRITICAL email
    assert alert_emailer.send_pending_emails(db) == 0                      # not again
    assert mail_server[1]["subject"] == ("[PulseGuard] NOW CRITICAL: PT-0007 heart rate HIGH "
                                         "(155 bpm, limit 130), was WARNING")
    assert "getting worse" in mail_server[1]["body"]


def test_alert_that_ends_before_the_escalation_email_only_gets_resolved(db, mail_server):
    save_batch(db, [], [], [("opened", new_episode("PT-0007", "high", START, 130, 140, 31))])
    alert_emailer.send_pending_emails(db)
    over = new_episode("PT-0007", "high", START, 130, 155, 40)
    over["severity"], over["ended_at"] = "critical", START + timedelta(seconds=40)
    save_batch(db, [], [], [("closed", over)])
    alert_emailer.send_pending_emails(db)
    assert [m["subject"].split(":")[0] for m in mail_server] == ["[PulseGuard] WARNING", "[PulseGuard] RESOLVED"]


def test_alert_email_shows_trend_normal_range_and_chart_link(db, mail_server):
    with db.cursor() as cur:
        cur.execute("""INSERT INTO patients (customer_id, profile, age, resting_bpm, low_limit, high_limit)
                       VALUES ('PT-0007', 'senior', 80, 70, 50, 119)""")
    readings = [{"customer_id": "PT-0007", "recorded_at": START + timedelta(seconds=s),
                 "heart_rate": bpm, "status": "high"} for s, bpm in [(30, 128), (31, 135), (32, 141), (33, 142)]]
    save_batch(db, readings, [], [("opened", new_episode("PT-0007", "high", START, 119, 142, 34))])
    alert_emailer.send_pending_emails(db)
    body = mail_server[0]["body"]
    assert "heart rate HIGH for 33 s." in body                             # from the readings, not a guess
    assert "Last readings: 128 -> 135 -> 141 -> 142 bpm (rising)" in body
    assert "Normal for this patient: 50-119 bpm." in body
    assert "See the chart: http://localhost:3000/d/heartbeat-monitor?var-patient=PT-0007" in body

