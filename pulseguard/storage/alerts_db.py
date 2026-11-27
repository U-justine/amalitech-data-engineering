# Reads and updates health alerts (alert_episodes) in PostgreSQL.


# Alerts still open from last time, so they can close properly after a restart.
def load_open_episodes(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT episode_id, customer_id, kind, severity, limit_bpm, peak_bpm,
                              reading_count, started_at
                       FROM alert_episodes WHERE ended_at IS NULL""")
        columns = [c.name for c in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.commit()
    state = {}
    for episode in rows:
        episode["ended_at"] = None
        state[episode["customer_id"]] = {
            "kind": episode["kind"], "since": episode["started_at"], "count": episode["reading_count"],
            "peak": episode["peak_bpm"], "episode": episode,
        }
    return state


# Alerts that still need an email: new, got worse (warning -> critical), or ended.
# With min_severity="critical", warnings aren't emailed (you only see them in Grafana).
# If a warning later becomes critical, it gets emailed then.
# RESOLVED is only sent if the alert was emailed in the first place.
def episodes_needing_email(conn, min_severity="warning"):
    levels = ("critical",) if min_severity == "critical" else ("warning", "critical")
    with conn.cursor() as cur:
        cur.execute("""SELECT e.*, p.profile, p.age, p.low_limit, p.high_limit
                       FROM alert_episodes e LEFT JOIN patients p USING (customer_id)
                       WHERE (e.opened_email_at IS NULL AND e.severity IN %s)
                          OR (e.ended_at IS NULL AND e.severity = 'critical' AND e.emailed_severity = 'warning')
                          OR (e.ended_at IS NOT NULL AND e.closed_email_at IS NULL AND e.opened_email_at IS NOT NULL)
                       ORDER BY e.started_at""", (levels,))
        columns = [c.name for c in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.commit()
    return rows


# Write down that an email was sent. which = "opened", "escalated" or "closed".
# severity = what that email told the doctor, so I can notice if a warning becomes critical later.
def mark_emailed(conn, episode_id, which, severity=None):
    sql = {
        "opened": "UPDATE alert_episodes SET opened_email_at = now(), emailed_severity = %s WHERE episode_id = %s",
        "escalated": "UPDATE alert_episodes SET emailed_severity = %s WHERE episode_id = %s",
        "closed": "UPDATE alert_episodes SET closed_email_at = now() WHERE episode_id = %s",
    }[which]
    params = (episode_id,) if which == "closed" else (severity, episode_id)
    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()


# The patient's last few readings since the alert started: [(time, bpm), ...], oldest first.
def recent_readings(conn, customer_id, since, count=5):
    with conn.cursor() as cur:
        cur.execute("""SELECT recorded_at, heart_rate FROM readings
                       WHERE customer_id = %s AND recorded_at >= %s
                       ORDER BY recorded_at DESC LIMIT %s""", (customer_id, since, count))
        rows = cur.fetchall()
    conn.commit()
    return list(reversed(rows))
