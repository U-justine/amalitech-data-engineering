# Sends one email (all PulseGuard emails go through here).
#
# Test it:  python -m pulseguard.notifications.email_sender   then open http://localhost:8025
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage

from pulseguard import config


def send_email(subject, body, to=None):
    """Send one email. Returns True if sent.
    If it fails, print a warning (don't crash)."""
    if not config.EMAIL_ENABLED:
        return False

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = config.ALERT_FROM
    email["To"] = to or config.ALERT_TO
    email.set_content(body)

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            if config.SMTP_TLS:
                server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(email)
        print(f"Email sent to {email['To']}: {subject}")
        return True
    except (OSError, smtplib.SMTPException) as email_error:
        print(f"WARNING: could not send email ({email_error})", file=sys.stderr)
        return False


def when(moment=None):
    """A short, readable local time with its time zone: 25 Nov 2026, 17:08 (UTC+02:00)."""
    local = moment.astimezone() if moment else datetime.now().astimezone()
    offset = local.strftime("%z")                     # e.g. +0200
    return f"{local:%d %b %Y, %H:%M} (UTC{offset[:3]}:{offset[3:]})"


def how_long(seconds):
    """e.g. 75 -> '1 min 15 s', 4000 -> '1 h 6 min'."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60} s"
    return f"{seconds // 3600} h {seconds % 3600 // 60} min"


if __name__ == "__main__":
    sent = send_email("[PulseGuard] Test email", "This is a test email from PulseGuard. Everything is fine.")
    print("Open http://localhost:8025 to see it." if sent else "Email was NOT sent - is Mailpit running?")
