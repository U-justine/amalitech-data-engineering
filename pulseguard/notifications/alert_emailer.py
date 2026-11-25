# Emails the health alerts that still need one (used by alert_service.py).
#   - The database says WHAT still needs an email.
#   - After sending, the alert is marked "emailed" -> never sent twice.
#   - Email failed? It stays unmarked and is tried again later -> never lost.
import json

from pulseguard.notifications.health_alerts import send_health_alert
from pulseguard.storage.alerts_db import episodes_needing_email, mark_emailed


def send_pending_emails(conn):
    """Email every alert not emailed yet. Returns how many were sent."""
    sent = 0
    for episode in episodes_needing_email(conn):
        if episode["opened_email_at"] is None:
            if not send_health_alert("opened", episode):
                continue                      # retry later
            mark_emailed(conn, episode["episode_id"], "opened")
            sent += 1
        if episode["ended_at"] is not None and episode["closed_email_at"] is None:
            if send_health_alert("closed", episode):
                mark_emailed(conn, episode["episode_id"], "closed")
                sent += 1
    return sent


def process_alert_messages(consumer, conn):
    """Read alert messages (up to 1 s), then send the emails."""
    batch = consumer.poll(timeout_ms=1000)
    messages = [m for partition_messages in batch.values() for m in partition_messages]
    for m in messages:
        alert = json.loads(m.value)
        print(f"  alert message: {alert['event']} {alert['customer_id']} {alert['kind']} "
              f"({alert['severity']}, peak {alert['peak_bpm']} bpm)")
    if messages:
        send_pending_emails(conn)
        consumer.commit()   # only after the emails are handled
    return len(messages)
