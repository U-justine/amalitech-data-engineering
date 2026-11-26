# Health alert emails to doctors (ALERT_TO): alert raised / got worse (now critical) / back to normal.
# Self-check patients (TEST-...) go to the IT team instead, marked [TEST].
from pulseguard import config
from pulseguard.notifications.email_sender import how_long, send_email, when


def describe_patient(episode):
    if episode.get("profile"):
        return f"{episode['customer_id']} ({episode['profile']}, age {episode['age']})"
    return episode["customer_id"]


def is_test_patient(customer_id):
    """Self-check patients (TEST-...) are not real: their alerts go to the IT team, not doctors."""
    return customer_id.startswith("TEST-")


def trend(recent):
    """Last readings -> 'Last readings: 128 -> 135 -> 142 bpm (rising)', or "" if none."""
    values = [bpm for _, bpm in recent]
    if not values:
        return ""
    change = values[-1] - values[0]
    word = "rising" if change > 2 else "falling" if change < -2 else "steady"
    return f"Last readings: {' -> '.join(str(v) for v in values)} bpm ({word})\n"


def how_long_so_far(episode):
    """How long the patient has been out of range, from the readings we have."""
    recent = episode.get("recent") or []
    if not recent:
        return f"{config.EPISODE_MIN_SECONDS}+ seconds"
    return how_long((recent[-1][0] - episode["started_at"]).total_seconds())


def normal_range(episode):
    if episode.get("low_limit") is None or episode.get("high_limit") is None:
        return ""
    return f"Normal for this patient: {episode['low_limit']}-{episode['high_limit']} bpm.\n"


def chart_link(customer_id):
    return f"See the chart: {config.DASHBOARD_URL}?var-patient={customer_id}\n"


def send_health_alert(event, episode):
    """Health alert email. event = "opened", "escalated" (warning -> critical) or "closed"."""
    if is_test_patient(episode["customer_id"]):
        return send_test_alert(event, episode)
    patient = describe_patient(episode)
    kind = episode["kind"].upper()
    direction = "above" if episode["kind"] == "high" else "below"
    facts = (
        trend(episode.get("recent") or [])
        + f"Peak {episode['peak_bpm']} bpm, {direction} their limit of {episode['limit_bpm']} bpm, "
        f"since {when(episode['started_at'])}.\n"
        + normal_range(episode)
    )

    if event == "opened":
        subject = (f"[PulseGuard] {episode['severity'].upper()}: {episode['customer_id']} heart rate "
                   f"{kind} ({episode['peak_bpm']} bpm, limit {episode['limit_bpm']})")
        body = (
            f"{patient}: heart rate {kind} for {how_long_so_far(episode)}.\n"
            + facts
            + "\nPlease check on the patient.\n"
            + chart_link(episode["customer_id"])
            + f"\nRef: {episode['episode_id']}\n"
        )
    elif event == "escalated":
        subject = (f"[PulseGuard] NOW CRITICAL: {episode['customer_id']} heart rate {kind} "
                   f"({episode['peak_bpm']} bpm, limit {episode['limit_bpm']}), was WARNING")
        body = (
            f"{patient}: heart rate {kind} is getting worse, now CRITICAL "
            f"(out of range for {how_long_so_far(episode)}).\n"
            + facts
            + "\nPlease check on the patient now.\n"
            + chart_link(episode["customer_id"])
            + f"\nRef: {episode['episode_id']}\n"
        )
    else:
        seconds = (episode["ended_at"] - episode["started_at"]).total_seconds()
        subject = (f"[PulseGuard] RESOLVED: {episode['customer_id']} heart rate back to normal "
                   f"after {seconds:.0f} s")
        body = (
            f"{patient}: heart rate back to normal at {when(episode['ended_at'])}.\n"
            f"It was {episode['kind']} for {how_long(seconds)} (peak {episode['peak_bpm']} bpm, "
            f"limit {episode['limit_bpm']}).\n\n"
            f"No action needed.\n\n"
            f"Ref: {episode['episode_id']}\n"
        )
    return send_email(subject, body)


def send_test_alert(event, episode):
    """A self-check alert: short, marked [TEST], sent to the IT team only."""
    what = {"opened": "alert raised", "escalated": "alert escalated"}.get(event, "alert resolved")
    subject = f"[PulseGuard] [TEST] self-check {what} ({episode['customer_id']})"
    body = (f"Self-check test: {what} correctly. Not a real patient, no action needed.\n"
            f"Peak {episode['peak_bpm']} bpm, limit {episode['limit_bpm']}.\n")
    return send_email(subject, body, to=config.SYSTEM_ALERT_TO)
