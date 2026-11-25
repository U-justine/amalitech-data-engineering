# Health alert emails to doctors (ALERT_TO): alert raised / back to normal.
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


def send_health_alert(event, episode):
    """Health alert email. event = "opened" or "closed"."""
    if is_test_patient(episode["customer_id"]):
        return send_test_alert(event, episode)
    patient = describe_patient(episode)
    kind = episode["kind"].upper()
    direction = "above" if episode["kind"] == "high" else "below"

    if event == "opened":
        subject = (f"[PulseGuard] {episode['severity'].upper()}: {episode['customer_id']} heart rate "
                   f"{kind} ({episode['peak_bpm']} bpm, limit {episode['limit_bpm']})")
        body = (
            f"{patient}: heart rate {kind} for {config.EPISODE_MIN_SECONDS}+ seconds.\n"
            f"Peak {episode['peak_bpm']} bpm, {direction} their limit of {episode['limit_bpm']} bpm, "
            f"since {when(episode['started_at'])}.\n\n"
            f"Please check on the patient.\n\n"
            f"Ref: {episode['episode_id']}\n"
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
    what = "alert raised" if event == "opened" else "alert resolved"
    subject = f"[PulseGuard] [TEST] self-check {what} ({episode['customer_id']})"
    body = (f"Self-check test: {what} correctly. Not a real patient, no action needed.\n"
            f"Peak {episode['peak_bpm']} bpm, limit {episode['limit_bpm']}.\n")
    return send_email(subject, body, to=config.SYSTEM_ALERT_TO)
