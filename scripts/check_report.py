# After the self-check: explain the results in plain words, and remove the test patients.
import time


# The checks in 4 groups, for a plain-words email.
AREAS = [
    ("Saving heart rate readings",       lambda expected: expected in ("normal", "low", "high")),
    ("Setting aside faulty sensor data", lambda expected: expected.startswith("rejected")),
    ("Ignoring repeated readings",       lambda expected: expected == "duplicate"),
    ("Health alerts and their emails",   lambda expected: expected == "no alert" or expected.startswith("alert")),
]


def explain_results(results):
    """Check results -> plain words: (summary, likely cause, data lost?)."""
    summary, broken = [], set()
    for area, belongs in AREAS:
        in_area = [r for r in results if belongs(r[1])]
        good = sum(1 for r in in_area if r[3])
        if good == len(in_area):
            state = "working"
        else:
            state = f"NOT WORKING ({good} of {len(in_area)} {'check' if len(in_area) == 1 else 'checks'} passed)"
            broken.add(area)
        summary.append(f"{area + ' ':.<40} {state}")

    nothing_saved = {"Saving heart rate readings", "Setting aside faulty sensor data"} <= broken
    only_email = broken == {"Health alerts and their emails"} and any(
        "not emailed" in r[2] for r in results if not r[3])
    if nothing_saved:
        cause = "No readings reach the database: the consumer is probably not running, or the database is down."
        data_lost = "No, readings wait safely in Kafka."
    elif only_email:
        cause = "Alerts are found but not emailed: the alert service is probably not running, or email is down."
        data_lost = "No, alerts are saved and will be emailed later."
    else:
        cause = "Some checks gave unexpected results (a possible fault in PulseGuard)."
        data_lost = "Possibly, see below."
    return "\n".join(summary), cause, data_lost


def remove_test_data(conn, run_id, wait_for_resolved=True):
    """Delete this run's test patients (TEST-<run id>-...) from the database.
    First wait (up to 15 s) for the test alert's RESOLVED email, so the whole email path is used."""
    patients = f"TEST-{run_id}-%"
    with conn.cursor() as cur:
        for _ in range(15 if wait_for_resolved else 0):
            cur.execute("""SELECT count(*) FROM alert_episodes WHERE customer_id LIKE %s
                           AND opened_email_at IS NOT NULL AND closed_email_at IS NULL""", (patients,))
            if cur.fetchone()[0] == 0:
                break
            time.sleep(1)
        cur.execute("DELETE FROM readings WHERE customer_id LIKE %s", (patients,))
        cur.execute("DELETE FROM alert_episodes WHERE customer_id LIKE %s", (patients,))
        cur.execute("DELETE FROM rejected_readings WHERE raw_message LIKE %s", (f"%{run_id}%",))
    conn.commit()
