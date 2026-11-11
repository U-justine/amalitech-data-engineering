"""Quick test of the email settings, one step at a time.

I made this because it was hard to tell why emails weren't arriving.
Run it in the container:
    docker compose exec -w /opt/airflow/dags airflow-scheduler python -m flight_pipeline.check_email
    docker compose exec -w /opt/airflow/dags airflow-scheduler python -m flight_pipeline.check_email --send

without --send it only connects and logs in, with --send it also sends a test email
"""
from __future__ import annotations

import smtplib
import socket
import ssl
import sys

from .alerts import _smtp_settings, send_email


def _ok(msg):
    print(f"  [OK]   {msg}")


def _fail(msg, hint=""):
    print(f"  [FAIL] {msg}")
    if hint:
        print(f"         -> {hint}")
    sys.exit(1)


def main() -> None:
    s = _smtp_settings()
    pw = s["password"]
    print("1. Settings seen by Airflow")
    print(f"     SMTP_HOST      = {s['host'] or '(empty)'}")
    print(f"     SMTP_PORT      = {s['port']}")
    print(f"     SMTP_STARTTLS  = {s['starttls']}   SMTP_SSL = {s['ssl']}")
    print(f"     SMTP_USER      = {s['user'] or '(empty)'}")
    print(f"     SMTP_PASSWORD  = {('*' * 12 + pw[-2:]) if pw else '(empty)'}  ({len(pw.replace(' ', ''))} chars)")
    print(f"     SMTP_FROM      = {s['sender'] or '(empty)'}")
    print(f"     ALERT_EMAIL_TO = {', '.join(s['to']) or '(empty)'}")
    if not s["host"] or not s["to"]:
        _fail("SMTP_HOST or ALERT_EMAIL_TO is empty", "set them in docker-compose.yml / .env, then: docker compose up -d")
    if s["user"] and not pw:
        _fail("SMTP_PASSWORD is empty", "add SMTP_PASSWORD=<16-char Gmail App Password> to .env, then: docker compose up -d")
    if "gmail" in s["host"] and pw and len(pw.replace(" ", "")) != 16:
        print("  [WARN] Gmail App Passwords are 16 characters. Is this your normal password?")
    _ok("settings present")

    print(f"2. Network: can we reach {s['host']}:{s['port']}?")
    try:
        socket.create_connection((s["host"], s["port"]), timeout=10).close()
    except OSError as exc:
        _fail(f"cannot connect: {exc}", "check internet access from Docker, firewall/antivirus, and the port (587 or 465)")
    _ok("server reachable")

    print("3. Secure connection and login")
    try:
        if s["ssl"]:
            server = smtplib.SMTP_SSL(s["host"], s["port"], context=ssl.create_default_context(), timeout=30)
        else:
            server = smtplib.SMTP(s["host"], s["port"], timeout=30)
            if s["starttls"]:
                server.starttls(context=ssl.create_default_context())
                _ok("TLS encryption started")
        with server:
            if s["user"] and pw:
                server.login(s["user"], pw)
                _ok(f"logged in as {s['user']}")
            else:
                _ok("server accepts connections without login")
    except smtplib.SMTPAuthenticationError as exc:
        _fail(f"login refused: {exc.smtp_code} {exc.smtp_error.decode(errors='ignore')[:120]}",
              "Gmail: use a 16-char App Password (myaccount.google.com/apppasswords) with 2-Step Verification on")
    except Exception as exc:
        _fail(f"{type(exc).__name__}: {exc}")

    if "--send" in sys.argv:
        print(f"4. Sending a test alert to {', '.join(s['to'])}")
        if not send_email("[Airflow] Test alert: email is working",
                          "<h2 style='color:#1e8449'>Email alerts are working</h2>"
                          "<p>Sent by <code>flight_pipeline.check_email</code>.</p>"):
            _fail("sending failed (see the error above)")
        _ok("sent - check your inbox (and Spam the first time)")
    else:
        print("4. Skipped sending. Add --send to send a test email.")
    print("\nEmail connection is working.")


if __name__ == "__main__":
    main()
