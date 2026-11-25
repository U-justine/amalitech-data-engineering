# How long each step takes, for the consumer's summary line:
#   timing: producer -> consumer: avg 14 ms | saving: avg 63.7 ms per batch | total trip: about 78 ms
from datetime import datetime, timezone


def to_datetime(milliseconds):
    """Kafka time (ms since 1970) -> date and time."""
    if milliseconds is None:
        return None
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


def new_timing():
    """Empty timing numbers."""
    return {"batches": 0, "messages": 0, "delay_ms": 0.0, "max_delay_ms": 0.0, "save_ms": 0.0}


def add_timing(timing, delays, save_ms):
    """Add one batch (delays = ms each message took to arrive)."""
    timing["batches"] += 1
    timing["save_ms"] += save_ms
    timing["messages"] += len(delays)
    timing["delay_ms"] += sum(delays)
    timing["max_delay_ms"] = max([timing["max_delay_ms"]] + delays)


def timing_text(timing):
    """Timing numbers -> one readable line."""
    if not timing["batches"]:
        return "no new messages"
    avg_delay = timing["delay_ms"] / timing["messages"] if timing["messages"] else 0
    avg_save = timing["save_ms"] / timing["batches"]
    return (f"producer -> consumer: avg {avg_delay:.0f} ms (max {timing['max_delay_ms']:.0f} ms) "
            f"| saving: avg {avg_save:.1f} ms per batch "
            f"| total trip: about {avg_delay + avg_save:.0f} ms")
