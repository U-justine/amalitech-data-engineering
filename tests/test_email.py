# Proves that emails are REALLY sent, are short, and are in plain words.
#
# The mail_server fixture (in conftest.py) starts a real email server on this
# computer. The code sends real emails to it over SMTP, exactly as it would to
# Mailpit or Gmail, and each test checks what arrived in the inbox.

import pytest

from conftest import FakeKafkaConsumer
from helpers import consumer_without_patients
from pulseguard import config
from pulseguard.notifications.system_alerts import send_failure_email
from pulseguard.services import consumer


# ---------------------------------------------------------------- good cases

def test_email_is_really_sent(mail_server):
    assert send_failure_email("consumer", "could not connect to PostgreSQL", "full details here") is True

    assert len(mail_server) == 1
    email = mail_server[0]
    assert email["subject"] == ("[PulseGuard] SYSTEM PROBLEM: heart rates are not being checked "
                                "(database not reachable)")
    assert email["from"] == config.ALERT_FROM
    assert email["to"] == [config.SYSTEM_ALERT_TO]          # the IT team, not the clinical staff
    assert "full details here" in email["body"]


def test_system_problem_email_is_written_in_plain_words(mail_server):
    """Anyone can read the top of the email; the technical error is only at the bottom."""
    send_failure_email("consumer", "could not connect to PostgreSQL", "Traceback (most recent call last): ...")
    body = mail_server[0]["body"]
    plain, technical = body.split("Technical details (for the IT team)")
    assert "Heart rates are not being checked or saved" in plain
    assert "PulseGuard cannot reach its database." in plain
    assert "No, readings wait safely in Kafka." in plain
    assert "IT team: please check" in plain
    assert "Traceback" not in plain and "PostgreSQL" not in plain    # no code talk before the line
    assert "Traceback" in technical and "could not connect to PostgreSQL" in technical


@pytest.mark.parametrize("part, error, subject_end", [
    pytest.param("consumer", "Could not connect to Kafka at localhost:9092", "heart rates are not being checked (Kafka not reachable)", id="consumer, Kafka down"),
    pytest.param("alert service", "server closed the connection unexpectedly", "health alert emails are paused (database not reachable)", id="alert service, database down"),
    pytest.param("producer", KeyError("customer_id"), "no new heart rates are arriving (unexpected error)", id="producer, a bug"),
])
def test_subject_says_what_stopped_and_why(mail_server, part, error, subject_end):
    send_failure_email(part, error)
    assert mail_server[0]["subject"] == "[PulseGuard] SYSTEM PROBLEM: " + subject_end


def test_ctrl_c_does_not_send_an_email(mail_server, monkeypatch):
    """Stopping the consumer on purpose is not a failure."""
    class StopsWithCtrlC(FakeKafkaConsumer):
        def poll(self, timeout_ms=0):
            raise KeyboardInterrupt

    class Connection:
        def close(self):
            pass

    consumer_without_patients(monkeypatch)
    monkeypatch.setattr(consumer, "connect", lambda: Connection())
    monkeypatch.setattr(consumer, "connect_to_kafka", lambda: StopsWithCtrlC([]))
    monkeypatch.setattr("sys.argv", ["consumer.py", "--quiet"])
    consumer.main()
    assert mail_server == []



def test_email_server_down_does_not_crash(monkeypatch):
    """If the email server itself is down, we get a warning, not a second crash."""
    monkeypatch.setattr(config, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(config, "SMTP_PORT", 1)          # nothing listens on port 1
    monkeypatch.setattr(config, "EMAIL_ENABLED", True)
    assert send_failure_email("consumer", "database is down") is False


def test_no_email_when_turned_off(mail_server, monkeypatch):
    monkeypatch.setattr(config, "EMAIL_ENABLED", False)
    assert send_failure_email("consumer", "database is down") is False
    assert mail_server == []



# ---------------------------------------------------------------- emails are short

def test_system_problem_email_is_short(mail_server):
    """Long error details are cut to the useful end, so the email stays short."""
    long_traceback = "Traceback (most recent call last):\n" + "\n".join(f"  line {i}" for i in range(40))
    send_failure_email("consumer", "could not connect to PostgreSQL", long_traceback, retrying_every=10)
    body = mail_server[0]["body"]
    assert len(body.splitlines()) <= 20
    assert "line 39" in body and "line 5" not in body      # only the end of the error is kept


def test_health_alert_email_is_short(mail_server):
    from datetime import datetime, timezone
    from pulseguard.notifications.health_alerts import send_health_alert
    episode = {"episode_id": "PT-0007@x", "customer_id": "PT-0007", "profile": "athlete", "age": 20,
               "kind": "high", "severity": "critical", "limit_bpm": 170, "peak_bpm": 195, "reading_count": 31,
               "started_at": datetime(2026, 1, 1, 12, tzinfo=timezone.utc), "ended_at": None}
    send_health_alert("opened", episode)
    body = mail_server[0]["body"]
    assert body.startswith("PT-0007 (athlete, age 20): heart rate HIGH for 30+ seconds.")   # key fact first
    assert len(body.strip().splitlines()) <= 10                     # short enough to read at a glance
    assert "(UTC+" in body or "(UTC-" in body                       # the time says which time zone
