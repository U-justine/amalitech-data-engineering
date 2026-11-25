# Step 2 of the consumer: check each message,
# and label good readings normal / low / high with the patient's own limits.
import time

from pulseguard.processing.validator import check_reading, get_status
from pulseguard.simulation.patients import limits_for, load_limits
from pulseguard.storage.database import CONNECTION_PROBLEMS


def sort_messages(messages, quiet=False, sent_times=None, received_at=None, limits=None):
    """Split messages into good readings and rejected ones."""
    good, rejected = [], []
    for i, message in enumerate(messages):
        reading, problem = check_reading(message)
        if reading:
            if limits is not None:
                reading["status"] = get_status(reading["heart_rate"], *limits_for(limits, reading["customer_id"]))
            reading["sent_at"] = sent_times[i] if sent_times else None
            reading["received_at"] = received_at
            good.append(reading)
            if reading["status"] != "normal" and not quiet:
                print(f"  {reading['status'].upper():<4}  {reading['customer_id']}  {reading['heart_rate']} bpm")
        else:
            raw = message.decode("utf-8", errors="replace")
            rejected.append((raw, problem))
            if not quiet:
                print(f"  REJECTED ({problem}): {raw[:100]}")
    return good, rejected


def refresh_limits_if_needed(conn, state, readings):
    """New patient seen? Reload the limits (at most every 30 s)."""
    unknown = any(r["customer_id"] not in state["limits"] for r in readings)
    if unknown and time.time() - state["limits_loaded_at"] > 30:
        state["limits_loaded_at"] = time.time()
        try:
            state["limits"] = load_limits(conn)
        except CONNECTION_PROBLEMS:
            return        # database down: keep the old limits
        for reading in readings:
            reading["status"] = get_status(reading["heart_rate"], *limits_for(state["limits"], reading["customer_id"]))
