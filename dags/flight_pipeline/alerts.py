"""Email alerts for the pipeline.

What gets sent:
  RETRYING  - a task failed but will try again. always written to the alert
              log, emailed only if ALERT_EMAIL_ON_RETRY=true
  FAILED    - a task failed after all its retries
  TIMED OUT - a task ran past its execution_timeout and got killed
  SLOW TASK - a task worked but took longer than its threshold
              (config.SLOW_TASK_THRESHOLDS), e.g. the load taking minutes instead of seconds
  SLOW RUN  - the whole run took longer than config.SLOW_RUN_THRESHOLD_SECONDS
  SUCCESS   - optional summary after a good run

I send the emails myself with smtplib (settings come from .env). I tried
Airflow's own email settings first but they're different between Airflow
versions, this was simpler. If sending fails it just gets logged, an email
problem should never make the pipeline fail.

Retries and failures are also appended to data/alerts.log, so I have a record
even when the email doesn't arrive.
"""
from __future__ import annotations

import html
import logging
import os
import smtplib
import ssl
import time
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage

from . import config

log = logging.getLogger(__name__)


# --- sending ---
def _smtp_settings() -> dict:
    return {
        "host": os.getenv("SMTP_HOST", ""),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", ""),
        # gmail shows the app password with spaces ("abcd efgh ..."), remove them
        "password": (lambda pw, host: "".join(pw.split()) if "gmail" in host.lower() else pw.strip())(
            os.getenv("SMTP_PASSWORD", ""), os.getenv("SMTP_HOST", "")),
        "sender": os.getenv("SMTP_FROM") or os.getenv("SMTP_USER", ""),
        "starttls": os.getenv("SMTP_STARTTLS", "true").lower() == "true",
        "ssl": os.getenv("SMTP_SSL", "false").lower() == "true",
        "to": [a.strip() for a in os.getenv("ALERT_EMAIL_TO", "").split(",") if a.strip()],
    }


def send_email(subject: str, body_html: str) -> bool:
    """send an html email. True if it went out, False if skipped or it failed"""
    s = _smtp_settings()
    if not s["host"] or not s["to"]:
        log.warning("ALERT (email not configured: set SMTP_HOST and ALERT_EMAIL_TO): %s", subject)
        return False
    msg = EmailMessage(policy=policy.SMTP.clone(max_line_length=998))   # otherwise long subjects get split over 2 lines
    msg["Subject"] = subject
    msg["From"] = s["sender"] or "airflow@localhost"
    msg["To"] = ", ".join(s["to"])
    msg.set_content("This alert is HTML; open it in an HTML-capable mail client.")
    msg.add_alternative(body_html, subtype="html")
    try:
        if s["ssl"]:
            server = smtplib.SMTP_SSL(s["host"], s["port"], context=ssl.create_default_context(), timeout=30)
        else:
            server = smtplib.SMTP(s["host"], s["port"], timeout=30)
            if s["starttls"]:
                server.starttls(context=ssl.create_default_context())
        with server:
            if s["user"] and s["password"]:
                server.login(s["user"], s["password"])
            server.send_message(msg)
        log.info("Alert email sent to %s: %s", s["to"], subject)
        return True
    except Exception:  # an email problem shouldn't fail the task
        log.exception("Could not send alert email: %s", subject)
        return False


# --- building the message ---
def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")


def _elapsed(start) -> float | None:
    if not start:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - start).total_seconds()


# when each task started (filled by record_task_start).
# I needed this because ti.start_date was empty when testing with `airflow dags test`.
# the start and end callbacks run in the same process so a dict is fine
_TASK_STARTS: dict[tuple, float] = {}


def _ti_key(ti) -> tuple:
    return (getattr(ti, "dag_id", None), getattr(ti, "task_id", None),
            getattr(ti, "run_id", None), getattr(ti, "map_index", -1))


def record_task_start(context) -> None:
    """on_execute_callback - save the start time"""
    ti = context.get("ti") or context.get("task_instance")
    _TASK_STARTS[_ti_key(ti)] = time.monotonic()


def _task_duration(ti) -> float | None:
    started = _TASK_STARTS.get(_ti_key(ti))
    if started is not None:
        return time.monotonic() - started
    return _elapsed(getattr(ti, "start_date", None))


def _table(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#555'><b>{html.escape(k)}</b></td>"
        f"<td style='padding:4px 0'>{html.escape(str(v))}</td></tr>" for k, v in rows)
    return f"<table style='font-family:Arial,sans-serif;font-size:14px'>{cells}</table>"


def _body(title: str, colour: str, rows: list[tuple[str, str]], extra: str = "") -> str:
    return (f"<div style='font-family:Arial,sans-serif'>"
            f"<h2 style='color:{colour};margin:0 0 12px'>{html.escape(title)}</h2>"
            f"{_table(rows)}{extra}"
            f"<p style='color:#888;font-size:12px'>Sent by Airflow, DAG flight_price_pipeline (batch pipeline).</p></div>")


def _common_rows(context) -> list[tuple[str, str]]:
    ti = context.get("ti") or context.get("task_instance")
    rows = [
        ("DAG", getattr(ti, "dag_id", "?")),
        ("Task", getattr(ti, "task_id", "?")),
        ("Run ID", context.get("run_id") or getattr(ti, "run_id", "?")),
        ("Try number", str(getattr(ti, "try_number", "?"))),
    ]
    log_url = getattr(ti, "log_url", None)
    if log_url:
        rows.append(("Log", log_url))
    return rows


def _short_task_id(task_id: str) -> str:
    """'load.load_to_postgres' -> 'load_to_postgres', the thresholds use the short name"""
    return (task_id or "").split(".")[-1]


def append_alert_log(kind: str, context, message: str) -> None:
    """write one line per alert to alerts.log. never raises"""
    ti = context.get("ti") or context.get("task_instance")
    line = (f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | {kind} | "
            f"dag={getattr(ti, 'dag_id', '?')} | task={getattr(ti, 'task_id', '?')} | "
            f"run={context.get('run_id') or getattr(ti, 'run_id', '?')} | "
            f"try={getattr(ti, 'try_number', '?')} | {message}\n")
    try:
        os.makedirs(os.path.dirname(config.ALERT_LOG_PATH) or ".", exist_ok=True)
        with open(config.ALERT_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        log.exception("Could not write alert log %s", config.ALERT_LOG_PATH)
    log.warning("ALERT %s", line.strip())


def _error_text(exc) -> str:
    return f"{type(exc).__name__}: {exc}" if exc else "see task log"


# --- callbacks (set in default_args in the DAG) ---
def task_retry_alert(context) -> None:
    """on_retry_callback - a try failed, Airflow will try again.

    Always goes to alerts.log. Email only if ALERT_EMAIL_ON_RETRY=true, because
    most of the time the next retry works and I don't need an email for that.
    """
    ti = context.get("ti") or context.get("task_instance")
    task = getattr(ti, "task", None)
    exc = context.get("exception") or context.get("error")
    max_tries = getattr(task, "retries", "?")
    append_alert_log("RETRYING", context, f"retries configured={max_tries} | error={_error_text(exc)}")
    if config.ALERT_EMAIL_ON_RETRY:
        rows = _common_rows(context) + [
            ("Status", "RETRYING"),
            ("Retries configured", str(max_tries)),
            ("Error", _error_text(exc)),
        ]
        send_email(f"[Airflow] RETRYING: flight_price_pipeline.{getattr(ti, 'task_id', '?')}",
                   _body("Task failed, will retry", "#2e86c1", rows,
                         "<p>No action needed yet. You will get a FAILED email if all retries fail.</p>"))


def task_failure_alert(context) -> None:
    """on_failure_callback - the task failed for good (no retries left)"""
    ti = context.get("ti") or context.get("task_instance")
    exc = context.get("exception") or context.get("error")
    duration = _task_duration(ti)
    timeout = getattr(getattr(ti, "task", None), "execution_timeout", None)
    # on Airflow 3 the exception isn't always in the context, so I also check the run time against the timeout
    timed_out = type(exc).__name__ == "AirflowTaskTimeout" or bool(
        timeout and duration is not None and duration >= timeout.total_seconds() - 0.5)
    kind = "TIMED OUT" if timed_out else "FAILED"
    append_alert_log(kind, context, f"ran_for={_fmt_duration(duration)} | error={_error_text(exc)}")
    rows = _common_rows(context) + [
        ("Status", kind),
        ("Ran for", _fmt_duration(duration)),
        ("Error", _error_text(exc)),
    ]
    hint = ("<p>The task ran past its hard time limit (<code>execution_timeout</code>) and was stopped. "
            "Check the database load and connections.</p>" if timed_out else
            "<p>Downstream tasks did not run. PostgreSQL still has the last good load.</p>")
    send_email(f"[Airflow] {kind}: flight_price_pipeline.{getattr(ti, 'task_id', '?')}",
               _body(f"Task {kind.lower()}", "#c0392b", rows, hint))


def task_duration_check(context) -> None:
    """on_success_callback - email if the task worked but was slow"""
    ti = context.get("ti") or context.get("task_instance")
    task_id = getattr(ti, "task_id", "")
    threshold = config.SLOW_TASK_THRESHOLDS.get(_short_task_id(task_id), config.SLOW_TASK_DEFAULT_SECONDS)
    duration = _task_duration(ti)
    if duration is None or duration <= threshold:
        return
    rows = _common_rows(context) + [
        ("Status", "SUCCEEDED, but slow"),
        ("Duration", _fmt_duration(duration)),
        ("Threshold", _fmt_duration(threshold)),
    ]
    send_email(f"[Airflow] SLOW TASK: flight_price_pipeline.{task_id} took {_fmt_duration(duration)}",
               _body("Task slower than expected", "#d68910", rows,
                     "<p>The data is correct, but this step took longer than usual. "
                     "Check the database load, the file size, or the network between MySQL and PostgreSQL.</p>"))


def run_duration_check(context) -> None:
    """on the last task - email if the whole run was slow"""
    dag_run = context.get("dag_run")
    duration = _elapsed(getattr(dag_run, "start_date", None))
    if duration is None or duration < 0:   # `airflow dags test` gives weird run start dates, so use the task start times instead
        run_id = context.get("run_id") or getattr(dag_run, "run_id", None)
        starts = [v for k, v in _TASK_STARTS.items() if k[2] == run_id]
        duration = time.monotonic() - min(starts) if starts else None
    if duration is None or duration <= config.SLOW_RUN_THRESHOLD_SECONDS:
        return
    rows = [
        ("DAG", "flight_price_pipeline"),
        ("Run ID", context.get("run_id") or getattr(dag_run, "run_id", "?")),
        ("Status", "SUCCEEDED, but slow"),
        ("Run duration", _fmt_duration(duration)),
        ("Threshold", _fmt_duration(config.SLOW_RUN_THRESHOLD_SECONDS)),
    ]
    send_email(f"[Airflow] SLOW RUN: flight_price_pipeline took {_fmt_duration(duration)}",
               _body("Pipeline run slower than expected", "#d68910", rows))


def on_success(context) -> None:
    """used on the last task: check the task and the whole run"""
    task_duration_check(context)
    run_duration_check(context)


def run_summary_email(summary: dict, run_id: str) -> bool:
    """success email with the main numbers of the run (if send_success_email is on)"""
    rows = [("DAG", "flight_price_pipeline"), ("Run ID", run_id)] + [
        (k.replace("_", " ").capitalize(), str(v)) for k, v in summary.items()]
    return send_email(f"[Airflow] SUCCESS: flight_price_pipeline loaded {summary.get('rows_loaded', '?')} rows",
                      _body("Pipeline run succeeded", "#1e8449", rows))
