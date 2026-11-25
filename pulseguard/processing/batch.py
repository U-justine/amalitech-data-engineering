# Handles one batch of messages from Kafka (used by consumer.py).
#   1. take messages from Kafka
#   2. check them, label with the patient's own limits   (readings.py)
#   3. look for health alerts (30 s rule)                (alerts.py)
#   4. save it all; wait and retry if the database is down (storage/retry.py)
#   5. send alerts to the "heartbeat-alerts" topic
#   6. only then tell Kafka "done" (commit)
import time

from pulseguard.processing.alerts import find_alerts, print_alerts, publish_alerts
from pulseguard.processing.readings import refresh_limits_if_needed, sort_messages
from pulseguard.processing.timing import add_timing, to_datetime
from pulseguard.storage.database import save_batch
from pulseguard.storage.retry import save_until_it_works


def new_state(limits=None, open_episodes=None):
    """What the consumer remembers between batches."""
    return {
        "limits": limits or {},              # {patient id: (low, high)}
        "limits_loaded_at": time.time(),
        "episodes": open_episodes or {},     # {patient id: open alert}
    }


def process_one_batch(consumer, conn, totals, quiet=False, timings=(), state=None, alert_publisher=None,
                      retry=False):
    """One batch: take -> check -> find alerts -> save -> send alerts -> commit.
    retry=True: wait and retry if the database is down (the working connection goes in state["conn"]).
    Returns the number of messages in the batch (0 if there were none)."""
    state = state if state is not None else new_state()

    # 1. take a batch from Kafka
    records = [m for messages in consumer.poll(timeout_ms=1000).values() for m in messages]
    if not records:
        return 0
    received_at = time.time()
    sent_times = [to_datetime(getattr(m, "timestamp", None)) for m in records]   # stamped by Kafka

    # 2. check each reading
    good, rejected = sort_messages([m.value for m in records], quiet, sent_times,
                                   to_datetime(received_at * 1000), state["limits"])
    refresh_limits_if_needed(conn, state, good)

    # 3. look for health alerts
    events = find_alerts(state, good)

    # 4. save it all (database down? wait and retry the same batch)
    save_start = time.time()
    if retry:
        saved, state["conn"] = save_until_it_works(conn, good, rejected, events, consumer)
    else:
        saved = save_batch(conn, good, rejected, events)
    save_ms = (time.time() - save_start) * 1000

    # 5. send the alerts, 6. only now tell Kafka "done"
    publish_alerts(alert_publisher, events)
    consumer.commit()
    print_alerts(events)

    # totals and timing for the summary line
    totals["received"] += len(records)
    totals["saved"] += saved
    totals["duplicates"] += len(good) - saved
    totals["low_or_high"] += sum(1 for r in good if r["status"] != "normal")
    totals["rejected"] += len(rejected)
    totals["alerts"] = totals.get("alerts", 0) + sum(1 for event, _ in events if event == "opened")
    delays = [received_at * 1000 - m.timestamp for m in records if getattr(m, "timestamp", None)]
    for timing in timings:
        add_timing(timing, delays, save_ms)
    return len(records)
