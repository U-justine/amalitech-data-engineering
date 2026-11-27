# The self-check explains its results in plain words.

from scripts.check_cases import TESTS
from scripts.check_report import explain_results


# Self-check explained in plain words

def results(broken=()):
    """Pretend check results: every check passes except the ones whose expected value is in broken."""
    return [(d, e, "wrong" if e in broken else e, e not in broken) for d, _, e in TESTS]


def test_self_check_all_working():
    summary, cause, data_lost = explain_results(results())
    assert "NOT WORKING" not in summary
    assert summary.count("working") == 4


def test_self_check_only_alert_emails_broken():
    broken = results(broken={"alert:high:emailed"})
    broken = [(d, e, "alert:high:not emailed" if not ok else a, ok) for d, e, a, ok in broken]
    summary, cause, data_lost = explain_results(broken)
    assert "Health alerts and their emails ......... NOT WORKING (1 of 2 checks passed)" in summary
    assert "Saving heart rate readings ............. working" in summary
    assert "alert service is probably" in cause
    assert data_lost.startswith("No,")


def test_self_check_something_else_broken():
    summary, cause, data_lost = explain_results(results(broken={"duplicate"}))
    assert "Ignoring repeated readings ............. NOT WORKING (0 of 1 check passed)" in summary
    assert "unexpected results" in cause
    assert data_lost.startswith("Possibly,")
