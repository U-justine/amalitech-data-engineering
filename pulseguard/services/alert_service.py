# Emails health alerts.     python -m pulseguard.services.alert_service
#
# Reads the "heartbeat-alerts" topic as its own group ("alert-emailers").
#   - Kafka tells it when to look; the database tells it which alerts still need an email.
#   - After sending, the alert is marked "emailed" -> never sent twice.
#   - Email failed? It stays unmarked and is retried every 15 s -> never lost.
#   - Database down? Don't stop: email the IT team, wait, reconnect, carry on.
import time
import traceback

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from pulseguard.config import ALERT_GROUP_ID, ALERT_TOPIC, KAFKA_SERVER
from pulseguard.notifications.alert_emailer import process_alert_messages, send_pending_emails
from pulseguard.storage.database import CONNECTION_PROBLEMS, connect, reconnect
from pulseguard.notifications.back_online import report_back_online
from pulseguard.notifications.system_alerts import send_failure_email

RETRY_EVERY_SECONDS = 15        # retry failed emails
DATABASE_RETRY_SECONDS = 10     # wait while the database is down


# Connect to Kafka (keeps trying for a minute while it starts).
def connect_to_kafka():
    for attempt in range(20):
        try:
            return KafkaConsumer(
                ALERT_TOPIC,
                bootstrap_servers=KAFKA_SERVER,
                group_id=ALERT_GROUP_ID,
                enable_auto_commit=False,
                auto_offset_reset="earliest",
            )
        except NoBrokersAvailable:
            print("Kafka not ready yet, trying again...")
            time.sleep(3)
    raise SystemExit(f"Could not connect to Kafka at {KAFKA_SERVER}. Is 'docker compose up -d' running?")


# Start here. If the service crashes, email the IT team before stopping.
def main():
    try:
        run_alert_service()
    except (Exception, SystemExit) as error:
        send_failure_email("alert service", error, traceback.format_exc())
        raise


# One round: read alerts, send emails, cope if the database is down.
def one_round(consumer, status):
    try:
        if status["conn"] is None:
            raise CONNECTION_PROBLEMS[0]("no database connection")
        if status["database_down"]:
            sent = send_pending_emails(status["conn"])   # database answers: it's back
            status["database_down"] = False
            print(f"[{time.strftime('%H:%M:%S')}] Database is back. Sent {sent} waiting emails.")
            report_back_online("alert service")          # email: BACK ONLINE
        process_alert_messages(consumer, status["conn"])
        if time.time() - status["last_retry"] >= RETRY_EVERY_SECONDS:
            send_pending_emails(status["conn"])          # retry failed emails
            status["last_retry"] = time.time()
    except CONNECTION_PROBLEMS as error:
        # Database down: don't stop (alerts are safe in the database).
        # Tell the IT team once, wait, get a new connection, try again.
        if not status["database_down"]:
            send_failure_email("alert service", error, traceback.format_exc(),
                               retrying_every=DATABASE_RETRY_SECONDS)
            status["database_down"] = True
        print(f"[{time.strftime('%H:%M:%S')}] Database is down. Trying again in {DATABASE_RETRY_SECONDS} s...")
        time.sleep(DATABASE_RETRY_SECONDS)
        status["conn"] = reconnect(status["conn"])


# Connect, send anything left from last time, then keep going round until Ctrl+C.
def run_alert_service():
    conn = connect()
    consumer = connect_to_kafka()
    print(f"Watching topic '{ALERT_TOPIC}' for health alerts. Press Ctrl+C to stop.")
    report_back_online("alert service")   # was down before? email "back online"
    sent = send_pending_emails(conn)          # emails left over from last time
    if sent:
        print(f"Sent {sent} emails that were waiting.")
    status = {"conn": conn, "database_down": False, "last_retry": time.time()}
    try:
        while True:
            one_round(consumer, status)
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        if status["conn"] is not None:
            status["conn"].close()
        print("Alert service stopped.")


if __name__ == "__main__":
    main()
