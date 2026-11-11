"""Tests for the alert callbacks. send_email is faked, so no Airflow or mail server needed."""
import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dags"))

from flight_pipeline import alerts, config  # noqa: E402


class AirflowTaskTimeout(Exception):
    """same name as Airflow's timeout error, that's all the code looks at"""


@pytest.fixture
def sent(monkeypatch):
    box = []
    monkeypatch.setattr(alerts, "send_email", lambda subject, body: box.append((subject, body)) or True)
    alerts._TASK_STARTS.clear()
    return box


def _ctx(task_id="load_to_postgres", started_ago=0.0, timeout=None, exc=None, run_id="r1"):
    ti = SimpleNamespace(dag_id="flight_price_pipeline", task_id=task_id, run_id=run_id, map_index=-1,
                         try_number=1, start_date=None, task=SimpleNamespace(execution_timeout=timeout))
    ctx = {"ti": ti, "run_id": run_id, "exception": exc, "dag_run": SimpleNamespace(start_date=None, run_id=run_id)}
    alerts.record_task_start(ctx)
    alerts._TASK_STARTS[alerts._ti_key(ti)] -= started_ago
    return ctx


def test_failure_alert(sent):
    alerts.task_failure_alert(_ctx(exc=ValueError("boom")))
    assert sent[0][0] == "[Airflow] FAILED: flight_price_pipeline.load_to_postgres"
    assert "ValueError: boom" in sent[0][1]


def test_timeout_alert_by_exception_and_by_duration(sent):
    alerts.task_failure_alert(_ctx(exc=AirflowTaskTimeout("t")))
    alerts.task_failure_alert(_ctx(started_ago=11, timeout=timedelta(seconds=10)))
    assert all(s.startswith("[Airflow] TIMED OUT") for s, _ in sent)


def test_slow_task_only_when_over_threshold(sent):
    limit = config.SLOW_TASK_THRESHOLDS["load_to_postgres"]
    alerts.task_duration_check(_ctx(started_ago=limit - 5))
    assert sent == []
    alerts.task_duration_check(_ctx(started_ago=limit + 5))
    assert sent[0][0].startswith("[Airflow] SLOW TASK: flight_price_pipeline.load_to_postgres")


def test_slow_run(sent):
    alerts.run_duration_check(_ctx(task_id="check_source_file", started_ago=config.SLOW_RUN_THRESHOLD_SECONDS + 60))
    assert sent and sent[0][0].startswith("[Airflow] SLOW RUN")


def test_send_email_without_config_does_not_raise(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("ALERT_EMAIL_TO", raising=False)
    assert alerts.send_email("x", "<p>y</p>") is False


def test_send_email_failure_does_not_raise(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", "1")          # nothing runs on port 1
    monkeypatch.setenv("SMTP_STARTTLS", "false")
    monkeypatch.setenv("ALERT_EMAIL_TO", "a@b.c")
    assert alerts.send_email("x", "<p>y</p>") is False


def test_short_task_id_threshold_lookup(sent):
    limit = config.SLOW_TASK_THRESHOLDS["load_to_postgres"]
    assert alerts._short_task_id("load.load_to_postgres") == "load_to_postgres"
    alerts.task_duration_check(_ctx(task_id="load.load_to_postgres", started_ago=limit - 5))
    assert sent == []          # load.load_to_postgres should use the load threshold (120s), not the default


def test_retry_writes_fallback_log_and_no_email_by_default(sent, tmp_path, monkeypatch):
    log_file = tmp_path / "alerts.log"
    monkeypatch.setattr(config, "ALERT_LOG_PATH", str(log_file))
    monkeypatch.setattr(config, "ALERT_EMAIL_ON_RETRY", False)
    alerts.task_retry_alert(_ctx(task_id="extract.check_source_file", exc=FileNotFoundError("late")))
    line = log_file.read_text()
    assert "RETRYING" in line and "extract.check_source_file" in line and "FileNotFoundError" in line
    assert sent == []
    monkeypatch.setattr(config, "ALERT_EMAIL_ON_RETRY", True)
    alerts.task_retry_alert(_ctx(task_id="extract.check_source_file"))
    assert sent[0][0].startswith("[Airflow] RETRYING")


def test_failure_also_written_to_fallback_log(sent, tmp_path, monkeypatch):
    log_file = tmp_path / "alerts.log"
    monkeypatch.setattr(config, "ALERT_LOG_PATH", str(log_file))
    alerts.task_failure_alert(_ctx(exc=RuntimeError("db down")))
    assert "FAILED" in log_file.read_text() and sent
