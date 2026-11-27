# Health alerts in the consumer: find them, print them, and send them
# to the "heartbeat-alerts" topic (alert_service.py emails them).
# The 30-second rule itself is in episodes.py.
import json

from kafka import KafkaProducer

from pulseguard.config import ALERT_TOPIC, KAFKA_SERVER
from pulseguard.processing.episodes import update_episodes
from pulseguard.simulation.patients import limits_for


# Creates a Kafka producer for the alerts topic, waiting for Kafka to confirm storage.
def connect_alert_publisher():
    return KafkaProducer(
        bootstrap_servers=KAFKA_SERVER,
        key_serializer=lambda key: key.encode("utf-8"),
        value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
        acks="all",   # wait until Kafka has safely stored it
    )


# Checks every reading against the 30-second rule, in time order.
# Returns opened/escalated/closed events, plus the latest "updated" one per open alert.
def find_alerts(state, good):
    events, latest_update = [], {}
    for reading in sorted(good, key=lambda r: (r["customer_id"], r["recorded_at"])):
        low, high = limits_for(state["limits"], reading["customer_id"])
        for event, episode in update_episodes(state["episodes"], reading, low, high):
            if event == "updated":
                latest_update[episode["episode_id"]] = episode   # keep the newest only
            else:
                latest_update.pop(episode["episode_id"], None)
                events.append((event, episode))
    return events + [("updated", episode) for episode in latest_update.values()]


# Sends opened/escalated/closed alerts to the Kafka alerts topic, using the patient ID as the key.
def publish_alerts(alert_publisher, events):
    if alert_publisher is None or not events:
        return
    for event, episode in events:
        if event in ("opened", "escalated", "closed"):   # "updated" is for the database only
            alert_publisher.send(ALERT_TOPIC, key=episode["customer_id"], value={"event": event, **episode})
    alert_publisher.flush()   # make sure Kafka has them before we say "done"


# Prints a readable summary of each alert event to the terminal.
def print_alerts(events):
    for event, e in events:
        if event == "opened":
            print(f"  ALERT {e['severity'].upper()}: {e['customer_id']} heart rate {e['kind']} "
                  f"(limit {e['limit_bpm']}, peak {e['peak_bpm']} bpm) since {e['started_at'].astimezone():%H:%M:%S}")
        elif event == "escalated":
            print(f"  ALERT NOW CRITICAL: {e['customer_id']} heart rate {e['kind']} "
                  f"(limit {e['limit_bpm']}, peak {e['peak_bpm']} bpm)")
        elif event == "closed":
            print(f"  ALERT OVER: {e['customer_id']} back to normal "
                  f"(peak {e['peak_bpm']} bpm, {e['reading_count']} readings)")
