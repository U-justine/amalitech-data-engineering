# Reads and updates health alerts (alert_episodes) in PostgreSQL.


def load_open_episodes(conn):
    """Alerts still open from last time, so they can close properly after a restart."""
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


def episodes_needing_email(conn):
    """Alerts whose email (or "resolved" email) has not been sent yet."""
    with conn.cursor() as cur:
        cur.execute("""SELECT e.*, p.profile, p.age
                       FROM alert_episodes e LEFT JOIN patients p USING (customer_id)
                       WHERE e.opened_email_at IS NULL
                          OR (e.ended_at IS NOT NULL AND e.closed_email_at IS NULL)
                       ORDER BY e.started_at""")
        columns = [c.name for c in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.commit()
    return rows


def mark_emailed(conn, episode_id, which):
    """Note that an email was sent. which = "opened" or "closed"."""
    column = {"opened": "opened_email_at", "closed": "closed_email_at"}[which]
    with conn.cursor() as cur:
        cur.execute(f"UPDATE alert_episodes SET {column} = now() WHERE episode_id = %s", (episode_id,))
    conn.commit()
