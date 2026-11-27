# Sends the emails for health alerts. alert_service.py calls this.

# I ask the database which alerts haven't been emailed yet, send them,
# and mark each one as emailed so nobody gets the same email twice.

# If an email fails I don't mark it, so it gets sent next time instead of getting lost.

# By default I only email critical alerts. Too many emails and doctors start ignoring them.

# Warnings are still saved and you can see them in Grafana.

import json

from pulseguard import config
from pulseguard.notifications.health_alerts import send_health_alert
from pulseguard.storage.alerts_db import episodes_needing_email, mark_emailed, recent_readings


# Finds alerts that need an email, sends them, and marks them as sent.
# If an email fails, it skips marking it so it can try again next time.
def send_pending_emails(conn):
    sent = 0
    for episode in episodes_needing_email(conn, config.EMAIL_MIN_SEVERITY):
        episode["recent"] = recent_readings(conn, episode["customer_id"], episode["started_at"])
        if episode["opened_email_at"] is None:
            if not send_health_alert("opened", episode):
                continue                      # retry later
            mark_emailed(conn, episode["episode_id"], "opened", episode["severity"])
            sent += 1
        elif (episode["ended_at"] is None and episode["severity"] == "critical"
              and episode.get("emailed_severity") == "warning"):
            if send_health_alert("escalated", episode):   # got worse since the first email
                mark_emailed(conn, episode["episode_id"], "escalated", "critical")
                sent += 1
        if episode["ended_at"] is not None and episode["closed_email_at"] is None:
            if send_health_alert("closed", episode):
                mark_emailed(conn, episode["episode_id"], "closed")
                sent += 1
    return sent


# Reads alert messages from Kafka, sends the emails, and saves the Kafka position.
def process_alert_messages(consumer, conn):
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
