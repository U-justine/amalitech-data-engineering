# After a failure, the IT team gets one "back online" email when the part works again.

import psycopg2
import pytest

from conftest import FakeKafkaConsumer
from helpers import consumer_without_patients, no_waiting
from pulseguard import config
from pulseguard.notifications.system_alerts import send_failure_email
from pulseguard.services import consumer
from pulseguard.storage import database


# Back online

def test_back_online_email_after_a_failure(mail_server):
    from pulseguard.notifications.back_online import report_back_online
    send_failure_email("consumer", "could not connect to PostgreSQL")
    assert report_back_online("consumer") is True

    assert len(mail_server) == 2
    back = mail_server[1]
    assert back["subject"].startswith("[PulseGuard] BACK ONLINE: heart rates are being checked again (was down ")
    assert back["to"] == [config.SYSTEM_ALERT_TO]
    assert "Readings from the down time are being checked now" in back["body"]
    assert "Cause:     database not reachable" in back["body"]
    assert "No action needed." in back["body"]


def test_back_online_is_sent_only_once(mail_server):
    from pulseguard.notifications.back_online import report_back_online
    send_failure_email("alert service", "Could not connect to Kafka")
    assert report_back_online("alert service") is True
    assert report_back_online("alert service") is False     # already told
    assert len(mail_server) == 2


def test_normal_start_sends_no_back_online_email(mail_server):
    from pulseguard.notifications.back_online import report_back_online
    assert report_back_online("consumer") is False           # it was never down
    assert mail_server == []


# Failing again while already down must not reset the 'down since' time.
def test_downtime_counts_from_the_first_failure(mail_server, monkeypatch):
    import json
    from pulseguard.notifications import back_online
    send_failure_email("consumer", "could not connect to PostgreSQL")
    first = json.load(open(back_online.state_file("consumer")))["since"]
    send_failure_email("consumer", "could not connect to PostgreSQL")
    assert json.load(open(back_online.state_file("consumer")))["since"] == first


@pytest.mark.parametrize("seconds, text", [(42, "42 s"), (75, "1 min 15 s"), (4000, "1 h 6 min")])
def test_downtime_is_easy_to_read(seconds, text):
    from pulseguard.notifications.email_sender import how_long
    assert how_long(seconds) == text


# The real consumer.main(): first run, the database is down; second run, it works.
def test_consumer_down_then_restarted_sends_both_emails(mail_server, monkeypatch):
    def database_down(**settings):
        raise psycopg2.OperationalError("connection refused")

    no_waiting(monkeypatch)
    monkeypatch.setattr(database.psycopg2, "connect", database_down)
    monkeypatch.setattr("sys.argv", ["consumer.py", "--quiet"])
    with pytest.raises(SystemExit):
        consumer.main()                                       # run 1: fails

    class StopsWithCtrlC(FakeKafkaConsumer):
        def poll(self, timeout_ms=0):
            raise KeyboardInterrupt

    class Connection:
        def close(self):
            pass

    consumer_without_patients(monkeypatch)
    monkeypatch.setattr(consumer, "connect", lambda: Connection())
    monkeypatch.setattr(consumer, "connect_to_kafka", lambda: StopsWithCtrlC([]))
    consumer.main()                                           # run 2: starts fine, then Ctrl+C

    subjects = [m["subject"] for m in mail_server]
    assert subjects[0].startswith("[PulseGuard] SYSTEM PROBLEM: heart rates are not being checked")
    assert subjects[1].startswith("[PulseGuard] BACK ONLINE: heart rates are being checked again")
    assert len(subjects) == 2


# Error cases (back online)

# If the email server is down too, remember the problem and try again next start.
def test_back_online_is_kept_if_email_cannot_be_sent(monkeypatch):
    import os
    from pulseguard.notifications import back_online
    back_online.mark_down("consumer", "database not reachable")
    monkeypatch.setattr(config, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(config, "SMTP_PORT", 1)
    monkeypatch.setattr(config, "EMAIL_ENABLED", True)
    assert back_online.report_back_online("consumer") is False
    assert os.path.exists(back_online.state_file("consumer"))


def test_damaged_state_file_still_sends_back_online(mail_server):
    from pulseguard.notifications import back_online
    import os
    os.makedirs(config.STATE_DIR, exist_ok=True)
    open(back_online.state_file("producer"), "w").write("not json")
    assert back_online.report_back_online("producer") is True
    assert "(was down unknown)" in mail_server[0]["subject"]
