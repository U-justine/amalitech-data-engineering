# PulseGuard Runbook

What to do, step by step, to run PulseGuard and to respond to each email it sends.
Commands are for Windows PowerShell in the project folder, with `.venv\Scripts\activate` done.

---

## 1. Start everything

```powershell
docker compose up -d
docker compose ps
```

Wait until `hb-zookeeper`, `hb-kafka` and `hb-postgres` show **healthy**, and
`hb-kafka-init` has **exited (0)** (it creates the two topics).

Then open three windows:

| Window | Command | What it does |
|---|---|---|
| 1 | `python -m pulseguard.services.consumer --quiet` | checks and saves readings, finds health alerts |
| 2 | `python -m pulseguard.services.alert_service` | emails health alerts |
| 3 | `python -m pulseguard.services.producer` | streams 100 patients |

Useful pages: Mailpit inbox <http://localhost:8025>, Kafka UI <http://localhost:8080>,
Grafana dashboard <http://localhost:3000> (admin / admin).

## 2. Check that it is healthy

| Check | Healthy looks like |
|---|---|
| Consumer window | `received` and `saved` go up every 5 s; `producer -> consumer` delay is a few ms |
| `docker exec -it hb-postgres psql -U heartbeat -d heartbeat -c "SELECT * FROM open_alerts;"` | empty, or only patients you know about |
| Kafka UI → Consumers | group `heartbeat-savers` lag close to 0 |
| `python -m scripts.check_pipeline` | `19/19 passed` |

## 3. Stop everything

Ctrl+C in each window (this is a normal stop, so no email is sent), then:

```powershell
docker compose down        # keeps the data
docker compose down -v     # also deletes the database (fresh start)
```

---

## 4. Responding to emails

### 4.1 `[PulseGuard] WARNING / CRITICAL: PT-xxxx heart rate HIGH / LOW`

A patient has stayed outside their own heart rate limits for 30 seconds or more.
By default only **CRITICAL** alerts are emailed; WARNINGs appear in Grafana ("Open health alerts").
To email WARNINGs too, set `EMAIL_MIN_SEVERITY=warning` in `.env` and restart the alert service.

1. Read the email: patient, profile and age, how long it has lasted, the last readings and trend
   (rising / falling / steady), the limit crossed, peak bpm, start time and the patient's normal range.
   **See the chart** opens Grafana with that patient picked.
2. **CRITICAL** (20+ bpm above the high limit, or 10+ below the low limit): check on the
   patient straight away.
3. See the readings:
   ```sql
   SELECT recorded_at, heart_rate, status FROM readings
   WHERE customer_id = 'PT-0007' ORDER BY recorded_at DESC LIMIT 60;
   ```
4. If it gets worse (WARNING becomes CRITICAL) you get one more email,
   `[PulseGuard] NOW CRITICAL: ... was WARNING`: check on the patient now.
5. When the heart rate is back inside the limits you'll get a **RESOLVED** email. No action is needed.

### 4.2 `[PulseGuard] RESOLVED: PT-xxxx heart rate back to normal`

Information only. The full alert is in `alert_episodes`.

### 4.3 `[PulseGuard] SYSTEM PROBLEM: heart rates are not being checked (...)`

**If the cause is `database not reachable`, the consumer has NOT stopped.** It holds the
batch it was saving and tries again every 10 seconds. As soon as the database is back it
saves that batch, carries on, and sends a BACK ONLINE email. Usually you only need to make
sure the database comes back (`docker start hb-postgres`). **No readings are lost**: Kafka
keeps them, because the consumer only marks a batch "done" after saving it.

For any other cause (Kafka down at start-up, or a bug), the consumer has stopped and must be
restarted after fixing the cause.

The part in brackets is the cause: `database not reachable`, `Kafka not reachable` or
`unexpected error`. The exact error is in the email's "Technical details" section.

| Error in the email | Cause | Fix |
|---|---|---|
| `Could not connect to PostgreSQL` / `server closed the connection` / `terminating connection` | database down | `docker start hb-postgres` (or `docker compose up -d`) |
| `Could not connect to Kafka` / `NoBrokersAvailable` | Kafka down | `docker compose up -d`, wait for **healthy** |
| `relation "..." does not exist` | old database version | `docker compose down -v`, then `docker compose up -d` |
| anything else | a bug | read the Details section of the email (full error), fix, restart |

If it stopped, restart it with `python -m pulseguard.services.consumer --quiet`. It catches up on the waiting messages,
which shows as a large `producer -> consumer` delay at first, dropping back to milliseconds.

### 4.4 `[PulseGuard] SYSTEM PROBLEM: health alert emails are paused (...)`

Health alert emails are paused, but **no alert is lost**. Alerts are stored in
`alert_episodes`, and any not yet emailed are sent as soon as it works again.
If the cause is `database not reachable`, the alert service keeps running and tries again
every 10 seconds by itself; you get a BACK ONLINE email when it works. Otherwise fix the
cause as in 4.3, then run `python -m pulseguard.services.alert_service`.

To see alerts waiting for an email:
```sql
SELECT episode_id, kind, severity, started_at FROM alert_episodes WHERE opened_email_at IS NULL;
```

### 4.5 `[PulseGuard] SYSTEM PROBLEM: no new heart rates are arriving (...)`

New readings stopped arriving. Usually Kafka is down: `docker compose up -d`, then
`python -m pulseguard.services.producer`.

### 4.6 `[PulseGuard] SYSTEM PROBLEM: self-check failed (only N of 19 checks passed)`

The top of the email shows, in plain words, which areas are working or not
(saving readings, setting aside faulty data, ignoring repeats, health alerts and emails)
and the most likely reason. The check-by-check list is at the bottom, for the IT team.

| Failed checks | Likely cause |
|---|---|
| all of them, `not saved` / `not rejected` | the consumer is not running |
| only `35 s racing heart` with `alert:high:not emailed` | the alert service is not running, or Mailpit is down |
| one or two specific checks | a real bug: compare expected vs actual |

### 4.6b `[PulseGuard] [TEST] self-check alert raised / resolved (TEST-...)`

Sent to the IT team when you run the self-check: proof that the alert emails work.
Not a real patient. **No action needed.** The test patients are deleted when the check ends.

### 4.7 `[PulseGuard] BACK ONLINE: ... (was down N min)`

The part named in the subject has started again and is working. The email says how long it
was down and what the cause was. **No action is needed.** It is sent automatically the
first time the part starts successfully after a SYSTEM PROBLEM email.

How it works: when a part fails, it leaves a small file in `.pulseguard_state/`
(e.g. `consumer.down`). On its next successful start it finds the file, sends this email,
and deletes the file. To see which parts are currently marked as down:
```powershell
dir .pulseguard_state
```

### 4.8 No emails arrive at all

1. Is Mailpit running? `docker compose ps` should show `hb-mailpit`. Open <http://localhost:8025>.
2. Send a test: `python -m pulseguard.notifications.email_sender`.
3. If you see `WARNING: could not send email`, check the `SMTP_*` settings ([`.env.example`](.env.example)).

---

## 5. Common tasks

| Task | How |
|---|---|
| Demo a health alert | `python -m pulseguard.services.producer --emergency PT-0007` (or `--emergency-kind low`) |
| Demo a failure email and automatic recovery | with the consumer running: `docker stop hb-postgres`, wait 30 s, `docker start hb-postgres` |
| Read every message again | `$env:KAFKA_GROUP_ID="replay-1"; python -m pulseguard.services.consumer` (duplicates are skipped) |
| Handle more load | run [`consumer.py`](pulseguard/services/consumer.py) in up to 3 windows (3 partitions = up to 3 consumers) |
| Add more patients | `python -m pulseguard.services.producer --patients 500` (new patients are registered automatically) |
| Change a patient's limits | `UPDATE patients SET high_limit = 140 WHERE customer_id = 'PT-0007';` (the consumer picks it up when restarted) |
