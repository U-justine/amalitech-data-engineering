# "BACK ONLINE" emails to the IT team (SYSTEM_ALERT_TO).
#
# When a part fails I write a small note, e.g. .pulseguard_state/consumer.down, with the time.
# The next time it starts fine, I email "back online" and delete the note.
# I use a file and not the database, because the database might be the thing that's down.
import json
import os
import sys
from datetime import datetime

from pulseguard import config
from pulseguard.notifications.email_sender import how_long, send_email

# For each part: (words for the subject, one extra line or "")
WHAT_IS_BACK = {
    "consumer": ("heart rates are being checked again",
                 "Readings from the down time are being checked now."),
    "alert service": ("health alert emails are being sent again",
                      "Alerts that waited are being emailed now."),
    "producer": ("heart rates are arriving again", ""),
    "pipeline check": ("self-check passing again", ""),
}


def state_file(part):
    # where the "down" note for this part is kept
    return os.path.join(config.STATE_DIR, part.replace(" ", "_") + ".down")


# Writes the "I'm down" note with the time and the cause.
# If a note is already there I keep it, so I know when it really went down.
def mark_down(part, cause):
    try:
        os.makedirs(config.STATE_DIR, exist_ok=True)
        if not os.path.exists(state_file(part)):
            with open(state_file(part), "w") as f:
                json.dump({"since": datetime.now().isoformat(), "cause": cause}, f)
    except OSError as error:
        # can't write the file? just warn, don't crash
        print(f"WARNING: could not remember that {part} is down ({error})", file=sys.stderr)


# Call this when a part starts working. If it was down, email "back online"
# and delete the note. I only delete it after the email goes out.
def report_back_online(part):
    path = state_file(part)
    if not os.path.exists(path):
        return False                                   # wasn't down

    try:
        with open(path) as f:
            down = json.load(f)
        since = datetime.fromisoformat(down["since"])
        cause = down.get("cause", "")
    except (OSError, ValueError, KeyError):
        since, cause = None, ""                        # note is broken, still say it's back

    now = datetime.now()
    downtime = how_long((now - since).total_seconds()) if since else "unknown"

    short_effect, extra = WHAT_IS_BACK.get(part, (f"{part} is working again", ""))
    subject = f"[PulseGuard] BACK ONLINE: {short_effect} (was down {downtime})"
    body = (
        f"Good news: {short_effect}. No action needed.\n"
        + (f"{extra}\n" if extra else "")
        + f"\nDown for:  {downtime}"
        + (f" ({since.strftime('%H:%M')} to {now.strftime('%H:%M')})" if since else "") + "\n"
        + (f"Cause:     {cause}\n" if cause else "")
    )

    sent = send_email(subject, body, to=config.SYSTEM_ALERT_TO)
    if sent:
        os.remove(path)          # email went out, so the note can go
    return sent
