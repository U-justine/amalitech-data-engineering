# Shared helpers for the tests.
import os
import sys
import time
from types import SimpleNamespace

import pytest

# Let the tests import producer.py, consumer.py, etc. from the project folder.
PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_FOLDER)


# Pretends to be a Kafka consumer, so the consumer code can be tested without Kafka.
class FakeKafkaConsumer:

    def __init__(self, messages, batch_size=50):
        self.messages = messages
        self.batch_size = batch_size
        self.position = 0
        self.commits = 0

    def poll(self, timeout_ms=0):
        if self.paused:
            self.polls_while_paused += 1
            return {}
        batch = self.messages[self.position:self.position + self.batch_size]
        self.position += len(batch)
        if not batch:
            return {}
        # Like real Kafka, each message carries the time it was sent (in milliseconds).
        sent_ms = time.time() * 1000 - 50   # pretend it was sent 50 ms ago
        return {"partition-0": [SimpleNamespace(value=m, timestamp=sent_ms) for m in batch]}

    def commit(self):
        self.commits += 1

    def close(self):
        pass

    # Kafka's pause/resume: while paused, poll() returns nothing (used while waiting for the database)
    paused = False
    polls_while_paused = 0

    def assignment(self):
        return {"partition-0"}

    def pause(self, *partitions):
        self.paused = True

    def resume(self, *partitions):
        self.paused = False


# A clean test database. Tests using it are skipped if TEST_DB is not set.
@pytest.fixture
def db():
    dsn = os.getenv("TEST_DB")
    if not dsn:
        pytest.skip("set TEST_DB to run the database tests")
    import psycopg2
    conn = psycopg2.connect(dsn)
    with conn.cursor() as cur:
        cur.execute(open(os.path.join(PROJECT_FOLDER, "sql", "schema.sql")).read())
        cur.execute("TRUNCATE readings, rejected_readings, patients, alert_episodes")
    conn.commit()
    yield conn
    conn.close()


# Start a real email (SMTP) server on this computer for the test.
#
# Every email it receives is added to the returned list, so a test can
# check that an email was actually delivered, and read its subject and text.
@pytest.fixture
def mail_server(monkeypatch):
    import email
    import email.policy
    import socket
    from aiosmtpd.controller import Controller
    from pulseguard import config

    received = []

    class SaveEmails:
        async def handle_DATA(self, server, session, envelope):
            message = email.message_from_bytes(envelope.content, policy=email.policy.default)
            received.append({
                "from": envelope.mail_from,
                "to": envelope.rcpt_tos,
                # strip(): older Pythons (3.10) can leave a space in front of a long, wrapped subject
                "subject": str(message["Subject"]).strip(),
                "body": message.get_content(),
            })
            return "250 Message accepted"

    with socket.socket() as s:          # find a free port
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = Controller(SaveEmails(), hostname="127.0.0.1", port=port)
    server.start()
    monkeypatch.setattr(config, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(config, "SMTP_PORT", port)
    monkeypatch.setattr(config, "SMTP_TLS", False)
    monkeypatch.setattr(config, "SMTP_USER", "")
    monkeypatch.setattr(config, "EMAIL_ENABLED", True)
    yield received
    server.stop()


# Each test gets its own empty folder for the "is it down?" files,
# so tests never touch the real .pulseguard_state folder.
@pytest.fixture(autouse=True)
def separate_state_folder(tmp_path, monkeypatch):
    from pulseguard import config
    monkeypatch.setattr(config, "STATE_DIR", str(tmp_path / "state"))
    # Email warnings too, so the email tests cover every kind of alert email.
    # (The "only critical" setting has its own tests in test_alert_emails.py.)
    monkeypatch.setattr(config, "EMAIL_MIN_SEVERITY", "warning")
