# How long each step takes, for the consumer's summary line:
#   timing: producer -> consumer: avg 14 ms | saving: avg 63.7 ms per batch | total trip: about 78 ms
from datetime import datetime, timezone


# Kafka time (ms since 1970) -> date and time.
def to_datetime(milliseconds):
    if milliseconds is None:
        return None
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


# Empty timing numbers, to start counting.
def new_timing():
    return {"batches": 0, "messages": 0, "delay_ms": 0.0, "max_delay_ms": 0.0, "save_ms": 0.0}


# Add one batch to the totals (delays = ms each message took to arrive).
def add_timing(timing, delays, save_ms):
    timing["batches"] += 1
    timing["save_ms"] += save_ms
    timing["messages"] += len(delays)
    timing["delay_ms"] += sum(delays)
    timing["max_delay_ms"] = max([timing["max_delay_ms"]] + delays)


# Turn the timing numbers into one readable line.
def timing_text(timing):
    if not timing["batches"]:
        return "no new messages"
    avg_delay = timing["delay_ms"] / timing["messages"] if timing["messages"] else 0
    avg_save = timing["save_ms"] / timing["batches"]
    return (f"producer -> consumer: avg {avg_delay:.0f} ms (max {timing['max_delay_ms']:.0f} ms) "
            f"| saving: avg {avg_save:.1f} ms per batch "
            f"| total trip: about {avg_delay + avg_save:.0f} ms")
