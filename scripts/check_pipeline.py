# Self-check of the whole pipeline:  Kafka -> consumer -> database -> alert email
#
# Run with the consumer and alert service running:   python -m scripts.check_pipeline
#
# Sends 19 test messages (good, bad, a 20 s spike, a 35 s racing heart)
# and checks where each one ended up. Any failure -> email to the IT team.
# The test patients (TEST-...) are deleted afterwards, so they never mix with real ones.
#   The test messages:        check_cases.py
#   Plain words + clean-up:   check_report.py
import json
import os
import sys
import time
from datetime import datetime

# Let this file find the pulseguard package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from kafka import KafkaProducer

from pulseguard.config import DB_SETTINGS, KAFKA_SERVER, TOPIC
from pulseguard.notifications.back_online import report_back_online
from pulseguard.notifications.system_alerts import send_failure_email
from scripts.check_cases import RUN_ID, STORIES, TESTS, customer
from scripts.check_report import explain_results, remove_test_data


# 1. Send the test messages. Returns the text sent for each test.
def send_tests():
    producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER, acks="all")
    sent_text = []
    for _, message, _ in TESTS:
        if isinstance(message, str) and message.startswith("story:"):
            sent_text.append(message)
            for r in STORIES[message]:   # key = patient -> kept in order
                producer.send(TOPIC, key=r["customer_id"].encode(), value=json.dumps(r).encode())
            continue
        text = message if isinstance(message, str) else json.dumps(message)
        sent_text.append(text)
        producer.send(TOPIC, text.encode("utf-8"))
    producer.flush()
    producer.close()
    print(f"Sent {len(TESTS)} test messages (run id {RUN_ID}). Waiting for the consumer...")
    return sent_text


# 2. Wait (up to 30 s) until the test messages are handled.
# Returns (saved rows, rejected {message: reason}, alerts {patient: [...]}).
def wait_for_results(should_save, should_reject):
    conn = psycopg2.connect(**DB_SETTINGS)
    conn.autocommit = True
    for _ in range(30):
        with conn.cursor() as cur:
            cur.execute("SELECT customer_id, recorded_at, status FROM readings WHERE customer_id LIKE %s",
                        (f"TEST-{RUN_ID}-%",))
            story_patients = (customer(8), customer(9))
            saved = [row for row in cur.fetchall() if row[0] not in story_patients]
            cur.execute("SELECT raw_message, reason FROM rejected_readings WHERE raw_message LIKE %s",
                        (f"%{RUN_ID}%",))
            rejected = dict(cur.fetchall())   # raw message -> reason
            cur.execute("""SELECT customer_id, kind, opened_email_at IS NOT NULL FROM alert_episodes
                           WHERE customer_id LIKE %s""", (f"TEST-{RUN_ID}-%",))
            alerts = {}   # patient -> list of "alert:<kind>:<emailed or not>"
            for patient, kind, emailed in cur.fetchall():
                alerts.setdefault(patient, []).append(f"alert:{kind}:{'emailed' if emailed else 'not emailed'}")
        alert_done = alerts.get(customer(9)) == ["alert:high:emailed"]
        if len(saved) >= should_save and len(rejected) >= should_reject and alert_done:
            break
        time.sleep(1)
    conn.close()
    return saved, rejected, alerts


# 3. Compare what happened with what should have happened, and print a table.
# Returns a list of (description, expected, actual, ok).
def check_each_test(sent_text, saved, rejected, alerts, should_save):
    status_of = {(cust, recorded_at): status for cust, recorded_at, status in saved}
    results = []
    print(f"\n{'test':<24}{'expected':<34}{'actual':<34}result")
    print("-" * 98)
    for (description, message, expected), text in zip(TESTS, sent_text):
        if expected.startswith("rejected"):
            reason = rejected.get(text)
            actual = f"rejected:{reason}" if reason else "not rejected"
        elif expected == "duplicate":
            actual = "duplicate" if len(saved) == should_save else f"{len(saved)} rows saved"
        elif isinstance(message, str) and message.startswith("story:"):
            found = alerts.get(customer(int(message.split(":")[1])), [])
            actual = ", ".join(found) if found else "no alert"
        else:
            key = (message["customer_id"], datetime.fromisoformat(message["timestamp"]))
            actual = status_of.get(key, "not saved")
        ok = actual == expected
        results.append((description, expected, actual, ok))
        print(f"{description:<24}{expected:<34}{actual:<34}{'PASS' if ok else 'FAIL'}")
    print("-" * 98)
    return results


def main():
    sent_text = send_tests()
    should_save = sum(1 for *_, e in TESTS if e in ("normal", "low", "high"))
    should_reject = sum(1 for *_, e in TESTS if e.startswith("rejected"))
    saved, rejected, alerts = wait_for_results(should_save, should_reject)
    results = check_each_test(sent_text, saved, rejected, alerts, should_save)
    passed = sum(1 for *_, ok in results if ok)
    print(f"{passed}/{len(TESTS)} passed")

    # 4. Clean up: remove the test patients so they don't mix with real ones
    conn = psycopg2.connect(**DB_SETTINGS)
    remove_test_data(conn, RUN_ID)
    conn.close()
    print("Test patients removed from the database.")

    # 5. Any failure? Email the IT team.
    if passed < len(TESTS):
        failed = [f"  - {d}: expected {e}, got {a}" for d, e, a, ok in results if not ok]
        summary, cause, data_lost = explain_results(results)
        send_failure_email("pipeline check", f"only {passed} of {len(TESTS)} checks passed",
                           "Failed checks:\n" + "\n".join(failed),
                           plain_cause=cause, plain_summary=summary, data_lost=data_lost)
        return 1
    report_back_online("pipeline check")   # failed last time? email "passing again"
    return 0


if __name__ == "__main__":
    sys.exit(main())
