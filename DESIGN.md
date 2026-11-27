# PulseGuard: Design Notes

Why PulseGuard is built the way it is: how it uses Kafka, the main design decisions,
and the trade-offs behind them.

## 1. Kafka architecture, mapped to this project

| Kafka part | What it is | In PulseGuard |
|---|---|---|
| **Broker** | The Kafka server that stores messages | `hb-kafka` container, port 9092 |
| **ZooKeeper** | Keeps track of brokers and topic settings (older Kafka versions) | `hb-zookeeper` container |
| **Topic** | A named stream of messages | `heartbeats` (readings) and `heartbeat-alerts` (alerts) |
| **Partition** | A topic is split into ordered logs, so work can be shared | `heartbeats`: 3, `heartbeat-alerts`: 1 |
| **Message key** | Decides the partition; same key → same partition → kept in order | the patient id (`customer_id`) |
| **Producer** | Writes messages | [`producer.py`](pulseguard/services/producer.py), and [`consumer.py`](pulseguard/services/consumer.py) (writes alerts) |
| **Consumer group** | Consumers that share a topic's partitions | `heartbeat-savers` ([`consumer.py`](pulseguard/services/consumer.py)), `alert-emailers` ([`alert_service.py`](pulseguard/services/alert_service.py)) |
| **Offset** | A consumer's position in a partition | committed by hand, only after the work is done |

```
producer.py ──► [heartbeats: P0 P1 P2] ──► consumer.py (group heartbeat-savers) ──► PostgreSQL
                                                │
                                                └──► [heartbeat-alerts: P0] ──► alert_service.py (group alert-emailers) ──► email
```

Files: [`producer.py`](pulseguard/services/producer.py), [`consumer.py`](pulseguard/services/consumer.py), [`alert_service.py`](pulseguard/services/alert_service.py).

Two topics and two consumer groups mean alert emailing is **independent** of saving readings.
If emailing is slow or down, readings are still saved. More alert subscribers (SMS, a pager)
could be added later as new consumer groups, without changing [`consumer.py`](pulseguard/services/consumer.py).

## 2. Main design decisions

### 2.1 Every patient has their own limits
A fixed 50–120 bpm range treats a 25-year-old athlete and an 85-year-old the same.
PulseGuard stores a profile for each patient (`patients` table):

- **high limit** = 85% of maximum heart rate, where maximum = 220 − age
  (e.g. 170 at age 20, 119 at age 80)
- **low limit** = 40 for athletes (a slow resting heart is normal for them), 50 for everyone else

So 45 bpm is `normal` for an athlete but `low` for a senior, and 130 bpm is `normal` for a
young adult but `high` for an 80-year-old.

### 2.2 Alerts are episodes, not single readings
One high reading is usually a sensor glitch or a moment of effort. Emailing every one would
flood the inbox, and people would start ignoring it ("alert fatigue").
PulseGuard raises an alert only when a patient stays out of range for **30 seconds**:

- **one email when it starts** (warning, or critical if 20+ bpm above / 10+ below the limit)
- **one more email only if it gets worse** (warning becomes critical: "NOW CRITICAL"), so a doctor who
  read "warning" knows to hurry
- **one email when it ends** (resolved), with the peak and how long it lasted
- nothing else in between, however many readings arrive

Each alert email also shows how long it has lasted, the last 5 readings with a trend (rising,
falling, steady), the patient's normal range, the time with its time zone, and a link that opens
the Grafana dashboard with that patient already picked.

**Only CRITICAL alerts are emailed by default** (`EMAIL_MIN_SEVERITY=critical`). Hospitals tier alarms
the same way: urgent ones interrupt someone, the rest go on a screen. Every alert is still saved
and shown in Grafana, a WARNING that becomes CRITICAL is emailed at that moment, and an alert that
was never emailed gets no RESOLVED email either. The simulation's default event rate is also set
to a realistic level (about 4 medical events an hour for 100 patients); `--emergency` always
creates a CRITICAL event, so a demo still produces an email.

Each episode is one row in `alert_episodes`. The time is measured from the readings' own
timestamps, so the rule still works if some readings were lost or arrive in one batch.

### 2.3 The database is the source of truth for emails
[`alert_service.py`](pulseguard/services/alert_service.py) uses Kafka to know **when** to look, and the database to know **what**
still needs an email (`opened_email_at` / `closed_email_at` still empty). After sending,
it fills those in. As a result:

- a re-delivered Kafka message never sends a second email
- if the email server is down, the alert waits and is retried every 15 seconds
- if the alert service was stopped, waiting alerts are sent when it starts again

### 2.4 Failures are emailed, not just logged
If the consumer, producer, alert service or pipeline check fails, a `[PulseGuard] SYSTEM PROBLEM`
email is sent. Two kinds of people read PulseGuard's emails, so they are kept separate:

| Email | Goes to | Written for |
|---|---|---|
| Health alert (WARNING / CRITICAL / RESOLVED) | `ALERT_TO`, the clinical staff | doctors and nurses: patient, limit, peak, time; no technical words |
| System problem | `SYSTEM_ALERT_TO`, the IT / on-call team | anyone first: what stopped, why, whether data is lost, who to call; then the technical error for the IT team |
| Back online | `SYSTEM_ALERT_TO` | what works again, how long it was down, the cause; "no action is needed" |

All emails are short: the key fact on the first line, then why, whether data is lost, and
what happens next, in a few lines. Long error details are cut to their useful end.

Each problem is "closed" by a back-online email, like each health alert is closed by a
RESOLVED email, so nobody is left wondering whether it was fixed. The "down since" time is
kept in a small file (`.pulseguard_state/`), not in the database, because the database
may be the thing that failed. Ctrl+C is a normal stop and sends nothing.
[`RUNBOOK.md`](RUNBOOK.md) says what to do for each email.

### 2.5 A database outage doesn't stop the pipeline
If the database stops while the consumer is running, the consumer does not stop with it
(code: [`pulseguard/storage/retry.py`](pulseguard/storage/retry.py)):

1. it keeps the batch it was saving, and does **not** commit it to Kafka;
2. it emails the IT team once ("PulseGuard retries every 10 s and will email BACK ONLINE");
3. while it waits, it **pauses** its Kafka partitions but keeps calling `poll()`, so Kafka
   knows it is alive (if a consumer is silent for 5 minutes, Kafka gives its partitions to
   someone else);
4. every 10 seconds it throws away the old, dead connection and opens a **new** one (the old
   connection never works again once the database has restarted);
5. when the database answers, it saves **the same batch**, commits it to Kafka, resumes, and
   emails BACK ONLINE.

Only "can't reach the database" errors are retried. A bug, or a row the database refuses,
would fail forever, so those still stop the program with a SYSTEM PROBLEM email.
The alert service does the same: it keeps running, and sends any alerts that waited once the
database is back.

### 2.6 Small files, one job each
No Python file is longer than about 130 lines. [`consumer.py`](pulseguard/services/consumer.py) only starts things and loops;
[`processing/batch.py`](pulseguard/processing/batch.py) shows the order of the steps for one batch (poll, check, find alerts,
save, publish, commit), and each step's detail lives in its own small file:
[`processing/readings.py`](pulseguard/processing/readings.py), [`processing/alerts.py`](pulseguard/processing/alerts.py), [`processing/timing.py`](pulseguard/processing/timing.py), [`storage/retry.py`](pulseguard/storage/retry.py).
The same idea everywhere: emails are split by who gets them ([`notifications/`](pulseguard/notifications)), the
database code by what it handles ([`storage/database.py`](pulseguard/storage/database.py) for saving, [`storage/alerts_db.py`](pulseguard/storage/alerts_db.py)
for alerts), and the self-check into cases, steps and report ([`scripts/`](scripts)). So each file can be explained in one
sentence and tested on its own.

## 3. Kafka best practices followed

| Practice | How |
|---|---|
| Key messages for ordering | readings are keyed by patient id, so each patient's readings stay in time order, which the 30-second rule depends on |
| Durable writes | `acks="all"`: a send counts only once Kafka has stored it |
| Commit after processing | auto-commit is off; offsets are committed only after the database transaction and alert publishing succeed |
| Idempotent processing | `UNIQUE (customer_id, recorded_at)` and deterministic episode ids make replays harmless |
| Dead-letter handling | invalid messages go to `rejected_readings` with a reason, instead of crashing the consumer |
| Separate topics per purpose | readings and alerts are different streams with different consumers |
| Partitions sized for parallelism | 3 partitions allow up to 3 [`consumer.py`](pulseguard/services/consumer.py) instances to share the load |
| Monitor the pipeline itself | timing per step (`kafka_seconds`, `save_seconds`), failure emails, [`check_pipeline.py`](scripts/check_pipeline.py) |

## 4. Anti-patterns avoided

| Anti-pattern | Why it is bad | What PulseGuard does instead |
|---|---|---|
| Auto-commit before processing | a crash loses the messages that were committed but not saved | manual commit after saving |
| One message = one alert | alert fatigue; real problems get missed | 30-second episodes with one start and one end email |
| Alerts only in the logs | nobody reads logs at 3 a.m. | real emails, proven by tests and a recorded run |
| Crashing on bad data | one bad message stops the whole pipeline | validate, set aside in `rejected_readings`, carry on |
| No keys | a patient's readings can be processed out of order | keyed by patient id |
| One topic for everything | slow email sending would hold up saving readings | separate `heartbeat-alerts` topic and consumer group |
| Silent failure of the alert path | alerts lost when email is down | stored in the database and retried |
| Crashing when a dependency blips | a 10-second database restart needs a person to restart the pipeline | wait and retry the same batch, with a fresh connection, then carry on |
| Retrying everything | a bug is retried forever and hides the real problem | only connection problems are retried; bugs stop with an email |

## 5. Trade-offs ("nothing comes cheap")

| Choice | What we gain | What it costs |
|---|---|---|
| At-least-once delivery (commit after saving) | no reading is ever lost | duplicates are possible, so every write must handle repeats |
| `acks="all"` | messages survive a broker failure | a little slower per message |
| 30-second alert rule | far fewer false alarms | a real problem is reported up to 30 s later |
| Database-tracked emails | no lost or repeated emails | an extra table and a database query per alert |
| 3 partitions | up to 3 parallel consumers | more partitions = more broker resources; more consumers than partitions sit idle |
| Separate alerts topic | emailing can't slow down saving | one more topic and one more service to run |
| Personal limits | more accurate alerts | patient profiles must be kept up to date |
| ZooKeeper (Confluent 7.6 / Kafka 3.6) | the setup taught in class, widely documented | Kafka 4.0 removed ZooKeeper in favour of KRaft mode, so a production system today would use KRaft |
| Wait and retry on database outages | no restart needed; no data lost | while it waits, nothing new is checked; a very long outage builds a backlog in Kafka |
| Running Kafka ourselves in Docker | free, full control, good for learning | we do all the operations; a managed service (Confluent Cloud, Amazon MSK) costs money but handles them |

## 6. Known limits (future work)

- **Security:** passwords are in the files, Kafka has no login or encryption, and the ports
  are open to the local network. Next steps: secrets in `.env`, ports bound to `127.0.0.1`,
  separate read-only and write-only database users, and SASL/TLS for Kafka.
- **Patient limit changes** are picked up when the consumer restarts.
- **Episode state** is kept in memory and restored from the database on restart. If the
  consumer crashes mid-alert, the reading count for that alert may be slightly off.
