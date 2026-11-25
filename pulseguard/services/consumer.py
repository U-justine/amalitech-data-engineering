# Reads readings from Kafka, checks them, saves them, and raises health alerts.
#
#   python -m pulseguard.services.consumer           show every LOW/HIGH/REJECTED reading
#   python -m pulseguard.services.consumer --quiet   show only alerts and a summary
#
# This file starts things and keeps looping.
# What happens to each batch (check, alerts, save, commit) is in processing/batch.py.
#
# Nothing is lost: stop before step 6 and Kafka sends the batch again
# (the database skips readings it already has).
import argparse
import time
import traceback

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from pulseguard.config import ALERT_TOPIC, GROUP_ID, KAFKA_SERVER, TOPIC
from pulseguard.notifications.back_online import report_back_online
from pulseguard.notifications.system_alerts import send_failure_email
from pulseguard.processing.alerts import connect_alert_publisher
from pulseguard.processing.batch import new_state, process_one_batch
from pulseguard.processing.timing import new_timing, timing_text
from pulseguard.simulation.patients import load_limits
from pulseguard.storage.alerts_db import load_open_episodes
from pulseguard.storage.database import connect


def connect_to_kafka():
    """Connect to Kafka (keeps trying for a minute while it starts)."""
    for attempt in range(20):
        try:
            return KafkaConsumer(
                TOPIC,
                bootstrap_servers=KAFKA_SERVER,
                group_id=GROUP_ID,
                enable_auto_commit=False,      # we say "done" ourselves, after saving
                auto_offset_reset="earliest",  # first run: start from the oldest
            )
        except NoBrokersAvailable:
            print("Kafka not ready yet, trying again...")
            time.sleep(3)
    raise SystemExit(f"Could not connect to Kafka at {KAFKA_SERVER}. Is 'docker compose up -d' running?")


def main():
    parser = argparse.ArgumentParser(description="Save heart rate readings from Kafka into PostgreSQL")
    parser.add_argument("--quiet", action="store_true", help="only print alerts and a summary every 5 seconds")
    args = parser.parse_args()

    # Error? Email the IT team. (Ctrl+C = normal stop, no email.)
    try:
        run_consumer(args)
    except (Exception, SystemExit) as error:
        send_failure_email("consumer", error, traceback.format_exc())
        raise


def run_consumer(args):
    conn = connect()
    state = new_state(load_limits(conn), load_open_episodes(conn))
    state["conn"] = conn   # gets replaced if the database restarts
    consumer = connect_to_kafka()
    alert_publisher = connect_alert_publisher()
    print(f"Reading topic '{TOPIC}', saving to PostgreSQL, alerts to '{ALERT_TOPIC}'. "
          f"{len(state['limits'])} patients registered. Press Ctrl+C to stop.")
    report_back_online("consumer")   # was down before? email "back online"

    totals = {"received": 0, "saved": 0, "low_or_high": 0, "rejected": 0, "duplicates": 0, "alerts": 0}
    timing, all_timing = new_timing(), new_timing()   # last 5 seconds, whole run
    start = last_summary = time.time()
    try:
        while True:
            process_one_batch(consumer, state["conn"], totals, args.quiet, timings=(timing, all_timing),
                              state=state, alert_publisher=alert_publisher, retry=True)
            if time.time() - last_summary >= 5:
                print(f"[{time.strftime('%H:%M:%S')}] {totals}")
                print(f"           timing: {timing_text(timing)}")
                timing, last_summary = new_timing(), time.time()
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        alert_publisher.close()
        if state["conn"] is not None:
            state["conn"].close()
        print(f"Consumer stopped after {time.time() - start:.1f} seconds. Totals: {totals}")
        print(f"Timing for the whole run: {timing_text(all_timing)}")


if __name__ == "__main__":
    main()
