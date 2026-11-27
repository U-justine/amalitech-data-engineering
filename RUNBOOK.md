# PulseGuard Runbook

How to run PulseGuard from a clean start, test every part, and respond to each email it sends.
All commands are for Windows PowerShell. Do the steps **in order**, and don't go on until a
step shows what it should.

## The 5 windows

Open 5 PowerShell windows. In **each one**, go to the project folder first:

```powershell
cd C:\Users\User\Desktop\heartbeat-monitor
```

| Window | Used for | Activate `.venv`? |
|---|---|---|
| **Window 1** | Docker, checks and tests | yes |
| **Window 2** | consumer | yes |
| **Window 3** | alert service | yes |
| **Window 4** | producer | yes |
| **Window 5** | database (`psql`) | no |

To activate `.venv` in a window: `.venv\Scripts\activate` (the prompt then starts with `(.venv)`).

---

## 1. Run everything from scratch

### Step 1 (Window 1): delete everything from before

Stop any PulseGuard program still running (Ctrl+C in its window), then make sure no
Python process is left. An old producer left running sends a second reading every second
and makes the charts zigzag.

```powershell
Get-Process python -ErrorAction SilentlyContinue   # should show nothing
Stop-Process -Name python -Force                   # only if something is listed
```

(`Stop-Process` stops **every** Python program, so close other Python work first.)

Delete the containers, the database, the Kafka messages and the inbox:

```powershell
docker compose down -v
Remove-Item -Recurse -Force .pulseguard_state -ErrorAction SilentlyContinue
```

`-v` deletes the `pgdata` volume (the whole database). `.pulseguard_state` holds the
"was down" markers; deleting it stops old BACK ONLINE emails.

### Step 2 (Window 1): start the containers

Docker Desktop must be running (*Engine running*). If you get an `npipe` error, start it first.

```powershell
docker compose up -d
docker compose ps
```

Run `docker compose ps` again every few seconds. Go on only when `hb-zookeeper`, `hb-kafka`
and `hb-postgres` show **healthy** and `hb-kafka-init` shows **exited (0)**.

### Step 3 (Window 1): check the topics

```powershell
docker exec hb-kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic heartbeats
docker exec hb-kafka kafka-topics --bootstrap-server localhost:9092 --list
```

Expect `heartbeats` with `PartitionCount: 3`, and `heartbeat-alerts` in the list.

### Step 4 (Window 5): open the database

```powershell
docker exec -it hb-postgres psql -U heartbeat -d heartbeat
```

The prompt becomes `heartbeat=#`. Leave this window open: all queries in section 2 are typed
here. (Type `\q` to leave.) Check the database is new:

```sql
\dt
SELECT (SELECT count(*) FROM patients) AS patients,
       (SELECT count(*) FROM readings) AS readings,
       (SELECT count(*) FROM rejected_readings) AS rejected,
       (SELECT count(*) FROM alert_episodes) AS alerts;
```

Expect 4 tables (`alert_episodes`, `patients`, `readings`, `rejected_readings`) and
`0 | 0 | 0 | 0`. [`sql/schema.sql`](sql/schema.sql) created them when PostgreSQL first started.

### Step 5 (Window 2): start the consumer

```powershell
.venv\Scripts\activate
python -m pulseguard.services.consumer --quiet
```

Wait for: `Reading topic 'heartbeats', saving to PostgreSQL ... Press Ctrl+C to stop.`

### Step 6 (Window 3): start the alert service

```powershell
.venv\Scripts\activate
python -m pulseguard.services.alert_service
```

Wait for: `Watching topic 'heartbeat-alerts' for health alerts.`

### Step 7 (Window 4): start the producer

```powershell
.venv\Scripts\activate
python -m pulseguard.services.producer
```

Wait for: `Sending readings for 100 patients to topic 'heartbeats'.`
The producer always goes last, so the consumer and alert service are already listening.

### Step 8 (browser): open the pages

| Page | Address |
|---|---|
| Grafana dashboard | <http://localhost:3000> (admin / admin) |
| Kafka UI | <http://localhost:8080> |
| Mailpit inbox | <http://localhost:8025> |

Let it run for **2 to 3 minutes** before section 2, so there is data to look at.

---

## 2. Test everything

### Step 9 (Window 2): the consumer is keeping up

Every 5 seconds the consumer prints `received` and `saved` (both going up) and a timing line
where `producer -> consumer` is a few ms.

### Step 10 (Window 5): readings are being saved

```sql
SELECT (SELECT count(*) FROM readings)                          AS readings,
       (SELECT count(*) FROM readings WHERE status <> 'normal') AS low_or_high,
       (SELECT count(*) FROM rejected_readings)                 AS rejected;
```

Run it twice, a few seconds apart: `readings` grows by about 100 per second.

### Step 11 (Window 5): the newest readings

```sql
SELECT customer_id, recorded_at, heart_rate, status
FROM readings ORDER BY recorded_at DESC LIMIT 10;

SELECT * FROM latest_readings LIMIT 10;
```

Expect 10 rows with patients `PT-0001` to `PT-0100`, and `status` = `normal`, `low` or `high`.

### Step 12 (Window 5): patients and their own limits

```sql
SELECT profile, count(*) AS patients, min(age) AS youngest, max(age) AS oldest,
       round(avg(high_limit)) AS avg_high_limit, min(low_limit) AS lowest_low_limit
FROM patients GROUP BY profile ORDER BY profile;

SELECT customer_id, profile, age, low_limit, high_limit FROM patients ORDER BY customer_id LIMIT 5;
```

Expect 100 patients split into `athlete`, `adult`, `senior` (about 2 : 5 : 3).
`high_limit` = 85% of (220 − age); `low_limit` = 40 for athletes, 50 for the others.

### Step 13 (Window 5): status uses each patient's own limits

```sql
SELECT r.customer_id, p.low_limit, p.high_limit, r.heart_rate, r.status
FROM readings r JOIN patients p USING (customer_id)
WHERE r.status <> 'normal'
ORDER BY r.recorded_at DESC LIMIT 10;
```

Every `high` row has `heart_rate > high_limit`; every `low` row has `heart_rate < low_limit`.

### Step 14 (Window 5): bad data is set aside, not lost

```sql
SELECT reason, count(*) FROM rejected_readings GROUP BY reason ORDER BY count(*) DESC;

SELECT reason, raw_message, rejected_at FROM rejected_readings ORDER BY rejected_at DESC LIMIT 5;
```

Expect reasons such as `impossible_heart_rate`, and the original message kept in `raw_message`
(the producer sends about 2% sensor glitches on purpose).

### Step 15 (Window 5): no duplicates

```sql
SELECT customer_id, recorded_at, count(*)
FROM readings GROUP BY customer_id, recorded_at HAVING count(*) > 1;
```

Expect **0 rows**. The `UNIQUE (customer_id, recorded_at)` rule stops repeats.

### Step 16 (Window 5): the time index is used

```sql
EXPLAIN SELECT * FROM readings
WHERE recorded_at > (SELECT max(recorded_at) FROM readings) - interval '5 seconds';
```

Expect `Index Scan` (or `Bitmap Index Scan`) `using readings_time_idx`.

### Step 17 (Window 5): how fast each step is

```sql
SELECT customer_id, kafka_seconds, save_seconds, total_seconds
FROM readings ORDER BY saved_at DESC LIMIT 10;

SELECT * FROM timing_per_minute LIMIT 5;

SELECT round(avg(kafka_seconds), 3) AS avg_kafka_seconds,
       round(avg(save_seconds), 3)  AS avg_save_seconds,
       round(avg(total_seconds), 3) AS avg_total_seconds,
       max(total_seconds)           AS slowest_total_seconds
FROM readings WHERE saved_at > now() - interval '10 minutes';
```

Expect totals well under 1 second (usually under 0.1 s). `readings` per minute ≈ 6,000.

### Step 18 (Window 5): summary per patient

```sql
SELECT customer_id, count(*) AS readings, round(avg(heart_rate)) AS average_bpm,
       min(heart_rate) AS lowest, max(heart_rate) AS highest,
       count(*) FILTER (WHERE status <> 'normal') AS low_or_high
FROM readings WHERE recorded_at > now() - interval '10 minutes'
GROUP BY customer_id ORDER BY customer_id LIMIT 10;
```

### Step 19 (Window 4): start a health alert

Stop the normal producer and start it again with an emergency for one patient
(never run two producers at once):

```powershell
# Ctrl+C first, then:
python -m pulseguard.services.producer --emergency PT-0007
```

Wait **40 seconds** (the alert needs 30 s out of range). Window 2 prints the alert, and
Mailpit gets a `CRITICAL: PT-0007 heart rate HIGH` email.

### Step 20 (Window 5): the alert is in the database

```sql
SELECT * FROM open_alerts;

SELECT customer_id, kind, severity, limit_bpm, peak_bpm, started_at, ended_at,
       opened_email_at IS NOT NULL AS alert_emailed,
       closed_email_at IS NOT NULL AS resolved_emailed
FROM alert_episodes ORDER BY started_at DESC LIMIT 10;

SELECT recorded_at, heart_rate, status FROM readings
WHERE customer_id = 'PT-0007' ORDER BY recorded_at DESC LIMIT 20;
```

Expect `PT-0007` open, `critical`, `alert_emailed = t`, and its readings `high`.
About 1 to 2 minutes later `ended_at` is filled, `resolved_emailed = t`, and Mailpit has a
**RESOLVED** email. A low alert: `--emergency PT-0007 --emergency-kind low`.

### Step 21 (Window 1): database failure and recovery

```powershell
docker stop hb-postgres
```

Wait 30 seconds. Window 2 says it will try again every 10 s; Mailpit gets a
**SYSTEM PROBLEM** email. Then:

```powershell
docker start hb-postgres
```

Window 2 saves the waiting batch and carries on; Mailpit gets a **BACK ONLINE** email.
Window 5 lost its connection, so reconnect (`\q`, then Step 4's command) and check nothing was lost:

```sql
SELECT * FROM timing_per_minute LIMIT 5;
```

The minute of the outage shows a high `slowest_total_seconds` (readings waited in Kafka)
but no missing minute.

### Step 22 (Window 1): self-check of the whole pipeline

```powershell
.venv\Scripts\activate
python -m scripts.check_pipeline
```

Expect `19/19 passed`, and a `[TEST]` email in Mailpit. The test patients are deleted afterwards.

### Step 23 (Window 1): automated tests

```powershell
docker exec hb-postgres createdb -U heartbeat heartbeat_test
$env:TEST_DB="host=localhost port=5433 dbname=heartbeat_test user=heartbeat password=heartbeat"
pytest -q
```

Expect all tests passed (152). `createdb` is only needed after a fresh start.

### Step 24 (browser): check Grafana

Open <http://localhost:3000> → **PulseGuard** dashboard: the timing stats in ms, the three
profile charts (athletes, adults, seniors), and `PT-0007`'s alert. Pick a patient at the top
to see only them, with their limit lines.

---

## 3. Stop everything

Stop in the opposite order to starting. Ctrl+C is a normal stop, so no email is sent.

| Step | Window | Do |
|---|---|---|
| 25 | Window 4 | Ctrl+C (producer: no new readings) |
| 26 | Window 2 | Ctrl+C (consumer: after it saved the last batch) |
| 27 | Window 3 | Ctrl+C (alert service) |
| 28 | Window 5 | `\q` |
| 29 | Window 1 | `docker compose down` (keeps the data) or `docker compose down -v` (deletes everything) |

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
