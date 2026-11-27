# "SYSTEM PROBLEM" emails to the IT team (SYSTEM_ALERT_TO).
# Plain words on top, a short technical error at the bottom.
import socket

from pulseguard import config
from pulseguard.notifications.back_online import mark_down
from pulseguard.notifications.email_sender import send_email, when

# For each part: (subject words, what is happening, is data lost?)
WHAT_STOPPED = {
    "consumer": ("heart rates are not being checked",
                 "Heart rates are not being checked or saved, so no health alerts can be sent.",
                 "No, readings wait safely in Kafka."),
    "alert service": ("health alert emails are paused",
                      "Health alert emails are not being sent.",
                      "No, alerts are saved and will be emailed later."),
    "producer": ("no new heart rates are arriving",
                 "No new heart rates are arriving from the watches.",
                 "Yes, readings from this time are not recorded."),
    "pipeline check": ("self-check failed",
                       "The self-check found a part of PulseGuard that is not working.",
                       "Possibly, see below."),
}

# Common causes, found in the error text: (words to look for, subject words, plain words, runbook section)
CAUSES = [
    (("postgresql", "psycopg2", "server closed the connection", "could not receive data from server",
      "terminating connection", "connection refused"),
     "database not reachable", "PulseGuard cannot reach its database.", "4.3"),
    (("kafka", "nobrokersavailable", "kafkaerror", "kafkatimeout"),
     "Kafka not reachable", "PulseGuard cannot reach Kafka.", "4.3"),
    (("checks passed",),
     "", "Some test readings did not end up where they should.", "4.6"),
]


# Reads the error message and returns a short cause, a plain-English cause, and a runbook section.
def explain_error(error):
    text = f"{type(error).__name__} {error}".lower()
    for words, short, plain, section in CAUSES:
        if any(word in text for word in words):
            return short, plain, section
    return "unexpected error", "An unexpected error happened inside PulseGuard.", "4.3"


# Shortens long error tracebacks by keeping only the beginning and the most useful last few lines.
def short_details(details, keep=6):
    lines = details.strip().splitlines()
    if lines and lines[0].startswith("Traceback") and len(lines) > keep + 1:
        return "\n".join([lines[0], "  ..."] + lines[-keep:])
    return "\n".join(lines)


# Builds and sends a "SYSTEM PROBLEM" email to the IT team, and marks the part as down.
# retrying_every: set it when the part keeps trying by itself (e.g. every 10 s),
# so the email says to wait for BACK ONLINE instead of asking IT to fix it now.
def send_failure_email(what_failed, error, details="", plain_cause=None, plain_summary=None, data_lost=None,
                       retrying_every=None):
    short_effect, effect, standard_data_lost = WHAT_STOPPED.get(
        what_failed, (f"{what_failed} stopped", f"The {what_failed} has stopped.", "Unknown."))
    short_cause, cause, section = explain_error(error)
    if what_failed == "pipeline check":
        short_cause = (str(error).strip().splitlines() or [""])[0]   # "only 17 of 19 checks passed"
    cause = plain_cause or cause
    data_lost = data_lost or standard_data_lost

    if retrying_every is not None:
        next_step = (f"PulseGuard retries every {retrying_every} s and will email BACK ONLINE.\n"
                     f"No email soon? IT team: see RUNBOOK.md section {section}.")
    else:
        next_step = f"IT team: please check (RUNBOOK.md section {section})."

    subject = f"[PulseGuard] SYSTEM PROBLEM: {short_effect}" + (f" ({short_cause})" if short_cause else "")
    first_line = (str(error).strip().splitlines() or ["unknown error"])[0]
    body = (
        f"{effect}\n"
        + (f"\n{plain_summary}\n\n" if plain_summary else "")
        + f"Why:        {cause}\n"
        f"Data lost:  {data_lost}\n\n"
        f"{next_step}\n\n"
        f"{what_failed} on {socket.gethostname()}, {when()}\n\n"
        f"-- Technical details (for the IT team) --\n"
        f"{first_line}\n"
        + (f"{short_details(details)}\n" if details else "")
    )
    mark_down(what_failed, short_cause)
    return send_email(subject, body, to=config.SYSTEM_ALERT_TO)
