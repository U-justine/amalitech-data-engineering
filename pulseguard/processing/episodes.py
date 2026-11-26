# Decides when a patient needs a health alert.
#
# One bad reading is NOT an alert (it may be a glitch).
# An alert opens when a patient stays out of range for 30 seconds,
# and closes at their next normal reading.
#
#   normal, high, high ... (30 s) -> "opened" ... high -> "updated" ... normal -> "closed"
from pulseguard import config


def new_episode(customer_id, kind, since, limit_bpm, peak, count):
    """A new alert "ticket"."""
    return {
        "episode_id": f"{customer_id}@{since.isoformat()}",  # same patient + start time = same id
        "customer_id": customer_id,
        "kind": kind,
        "severity": "warning",
        "limit_bpm": limit_bpm,
        "peak_bpm": peak,
        "reading_count": count,
        "started_at": since,
        "ended_at": None,
    }


def severity_of(kind, peak, low_limit, high_limit):
    """Critical if far outside the limit, otherwise warning."""
    if kind == "high" and peak >= high_limit + config.CRITICAL_ABOVE:
        return "critical"
    if kind == "low" and peak <= low_limit - config.CRITICAL_BELOW:
        return "critical"
    return "warning"


def update_episodes(state, reading, low_limit, high_limit):
    """The main brain: takes one heartbeat, returns events ("opened", "updated", "closed").
    state = what we remember about each patient."""
    customer_id = reading["customer_id"]
    heart_rate = reading["heart_rate"]
    time = reading["recorded_at"]
    events = []

    # 1. Is this heartbeat high, low or normal?
    if heart_rate > high_limit:
        kind = "high"
    elif heart_rate < low_limit:
        kind = "low"
    else:
        kind = None

    # 2. Is this patient already out of range?
    current = state.get(customer_id)

    # 3. Back to normal (or high -> low)? Close the ticket and forget.
    if current and current["kind"] != kind:
        if current["episode"]:
            episode = current["episode"]
            episode["ended_at"] = time
            events.append(("closed", dict(episode)))   # send a copy
        del state[customer_id]
        current = None

    # 4. Normal heartbeat: nothing more to do.
    if kind is None:
        return events

    # 5. First bad heartbeat: start the timer. Then keep counting.
    if current is None:
        current = {"kind": kind, "since": time, "count": 0, "peak": heart_rate, "episode": None}
        state[customer_id] = current
    current["count"] += 1
    current["peak"] = max(current["peak"], heart_rate) if kind == "high" else min(current["peak"], heart_rate)

    limit = high_limit if kind == "high" else low_limit
    seconds_out = (time - current["since"]).total_seconds()

    # 6. Out of range for 30 seconds? Open a ticket.
    if current["episode"] is None and seconds_out >= config.EPISODE_MIN_SECONDS:
        current["episode"] = new_episode(customer_id, kind, current["since"], limit, current["peak"], current["count"])
        current["episode"]["severity"] = severity_of(kind, current["peak"], low_limit, high_limit)
        events.append(("opened", dict(current["episode"])))

    # 7. Ticket already open: update it (it can get worse: warning -> critical).
    elif current["episode"] is not None:
        episode = current["episode"]
        episode["peak_bpm"] = current["peak"]
        episode["reading_count"] = current["count"]
        new_severity = severity_of(kind, current["peak"], low_limit, high_limit)
        if new_severity == "critical" and episode["severity"] == "warning":
            episode["severity"] = "critical"
            events.append(("escalated", dict(episode)))    # got worse: the doctor must know
        else:
            events.append(("updated", dict(episode)))

    return events
