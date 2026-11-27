# Connects to PostgreSQL and saves each batch.
# (Reading and updating alerts is in alerts_db.py.)
import time

import psycopg2

from pulseguard.config import DB_SETTINGS


# "Can't reach the database" errors: worth waiting for and trying again.
# Other errors (bugs, refused rows) are not retried: they would fail again.
CONNECTION_PROBLEMS = (psycopg2.OperationalError, psycopg2.InterfaceError)


def reconnect(old_conn):
    """Close the old (dead) connection and try once to open a new one.
    After a database restart the old connection never works again.
    Returns the new connection, or None if the database is still down."""
    if old_conn is not None:
        try:
            old_conn.close()
        except Exception:
            pass                      # already broken: fine
    try:
        return psycopg2.connect(**DB_SETTINGS)
    except psycopg2.OperationalError:
        return None                   # still down


def connect():
    """Connect to the database (keeps trying for a minute while it starts)."""
    for attempt in range(30):
        try:
            return psycopg2.connect(**DB_SETTINGS)
        except psycopg2.OperationalError as error:
            print(f"Database not ready yet ({error}), trying again...")
            time.sleep(2)
    raise SystemExit("Could not connect to PostgreSQL. Is 'docker compose up -d' running?")


def save_batch(conn, good_readings, rejected, episode_events=()):
    """Save readings, rejected messages and alerts in one go.
    Returns how many new readings were saved (duplicates are skipped)."""
    saved = 0
    try:
        with conn.cursor() as cur:
            for r in good_readings:
                cur.execute(
                    """INSERT INTO readings
                           (customer_id, recorded_at, heart_rate, status, sent_at, received_at)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (customer_id, recorded_at) DO NOTHING""",
                    (r["customer_id"], r["recorded_at"], r["heart_rate"], r["status"],
                     r.get("sent_at"), r.get("received_at")),
                )
                saved += cur.rowcount   # 1 = saved, 0 = duplicate

            for raw_message, problem in rejected:
                cur.execute(
                    "INSERT INTO rejected_readings (raw_message, reason) VALUES (%s, %s)",
                    (raw_message, problem),
                )

            for event, e in episode_events:
                # Same alert again (after a restart)? Update it, don't fail.
                cur.execute(
                    """INSERT INTO alert_episodes (episode_id, customer_id, kind, severity, limit_bpm,
                                                   peak_bpm, reading_count, started_at, ended_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (episode_id) DO UPDATE SET
                           severity = EXCLUDED.severity, peak_bpm = EXCLUDED.peak_bpm,
                           reading_count = EXCLUDED.reading_count,
                           ended_at = COALESCE(EXCLUDED.ended_at, alert_episodes.ended_at)""",
                    (e["episode_id"], e["customer_id"], e["kind"], e["severity"], e["limit_bpm"],
                     e["peak_bpm"], e["reading_count"], e["started_at"], e["ended_at"]),
                )
        conn.commit()       # save the whole batch together
    except Exception:
        try:
            conn.rollback()     # save nothing from this batch
        except psycopg2.Error:
            pass                # connection already broken: nothing to undo
        raise                   # report the real error
    return saved
