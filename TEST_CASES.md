# PulseGuard Test Cases

Two kinds of tests:

1. **Automated tests** (`pytest`, in [`tests/`](tests)). These test each part on its own. Kafka is replaced by a small fake; the database tests use a real PostgreSQL test database; the email tests send real emails to a real email server started inside the test.
2. **End-to-end check** ([`check_pipeline.py`](scripts/check_pipeline.py)). This sends real messages through Kafka to the running consumer and alert service, and checks what ends up in PostgreSQL and whether the alert was emailed.

Each test is a **Good** case (valid input: it should work) or an **Error** case (bad input or a failure: it must be caught and handled safely).

## Summary

| | Good | Error | Total | Passed |
|---|---|---|---|---|
| Automated tests (pytest) | 70 | 69 | 139 | 139 |
| End-to-end check | 7 | 12 | 19 | 19 |

## What the error cases prove

| Failure | How PulseGuard handles it | Tests |
|---|---|---|
| Broken, empty or unreadable message | Saved in `rejected_readings` as `invalid_json`; the consumer keeps running | validator, consumer, end-to-end |
| Missing or wrong fields (customer, timestamp, heart rate) | Rejected with a clear reason | validator, end-to-end |
| Impossible heart rate (0, negative, 24, 231, 300, NaN) | Rejected as `impossible_heart_rate` / `heart_rate_not_a_number` | validator, end-to-end |
| Bad or future timestamp | Rejected as `invalid_timestamp` / `future_timestamp` | validator, end-to-end |
| Short spike or single glitch | Saved as high/low, but **no** alert and no email | episodes, alerts, end-to-end |
| Same message delivered twice | Second copy skipped: no duplicate reading, alert or email | consumer, database, alerts, end-to-end |
| Consumer restarts during an alert | The open alert is restored from the database and closes normally | alerts |
| Email server down | The alert waits in the database and is emailed when it is back | alerts, email |
| Database down while running | Keeps the same batch, emails once, retries every 10 s with a new connection, saves the batch when it's back, emails BACK ONLINE; nothing lost or duplicated | retry |
| Database down at start-up | Retries for a minute, then stops with a SYSTEM PROBLEM email; batch never committed, so nothing is lost | consumer, email |
| Kafka down | Producer/consumer/alert service retry, then stop and send a SYSTEM PROBLEM email | producer, consumer, email |
| Bad row reaches the database | Database rules (CHECK, NOT NULL, length) refuse it; the whole batch is rolled back | database, patients |
| Pipeline check fails | A SYSTEM PROBLEM email lists the failed checks | email |
| A failed part starts working again | One BACK ONLINE email with how long it was down; sent once, kept for later if email is down | email |

## Automated test cases (pytest)

Run with `pytest -v`. To include the database tests, set `TEST_DB` first (see the README).

### Simulated heart rates ([generator.py](pulseguard/simulation/generator.py))  ([`tests/test_generator.py`](tests/test_generator.py))

| # | Test case | Type | Result |
|---|---|---|---|
| T01 | Reading has the three lab fields | Good | PASS |
| T02 | Normal life stays inside each patients limits | Good | PASS |
| T03 | Heart rate changes gradually | Good | PASS |
| T04 | Medical event goes above high limit and stays | Good | PASS |
| T05 | Medical event low | Good | PASS |
| T06 | Glitches happen at the bad chance rate | Good | PASS |

### Patient profiles and personal limits ([patients.py](pulseguard/simulation/patients.py))  ([`tests/test_patients.py`](tests/test_patients.py))

| # | Test case | Type | Result |
|---|---|---|---|
| T07 | High limit depends on age: 20 years old | Good | PASS |
| T08 | High limit depends on age: 40 years old | Good | PASS |
| T09 | High limit depends on age: 80 years old | Good | PASS |
| T10 | Profiles have sensible limits | Good | PASS |
| T11 | Same heart rate means different things for different patients | Good | PASS |
| T12 | Unregistered patient gets clinic defaults | Good | PASS |
| T13 | Patients are registered once | Good | PASS |
| T14 | Database refuses bad patients: unknown profile | Error | PASS |
| T15 | Database refuses bad patients: age 150 | Error | PASS |
| T16 | Database refuses bad patients: low limit above high limit | Error | PASS |

### Producer ([producer.py](pulseguard/services/producer.py))  ([`tests/test_producer.py`](tests/test_producer.py))

| # | Test case | Type | Result |
|---|---|---|---|
| T17 | Producer sends json with customer key | Good | PASS |
| T18 | Producer gives up if kafka is down | Good | PASS |
| T19 | Emergency for unknown patient stops with a message | Good | PASS |
| T20 | Bad chance of one makes every reading bad | Good | PASS |

### Validation ([validator.py](pulseguard/processing/validator.py))  ([`tests/test_validator.py`](tests/test_validator.py))

| # | Test case | Type | Result |
|---|---|---|---|
| T21 | Status: resting | Good | PASS |
| T22 | Status: lowest normal (50) | Good | PASS |
| T23 | Status: highest normal (120) | Good | PASS |
| T24 | Status: just below normal (49) | Good | PASS |
| T25 | Status: lowest possible (25) | Good | PASS |
| T26 | Status: just above normal (121) | Good | PASS |
| T27 | Status: highest possible (230) | Good | PASS |
| T28 | Good message | Good | PASS |
| T29 | Decimal heart rate is rounded | Good | PASS |
| T30 | Timestamp ending in z is accepted | Good | PASS |
| T31 | Timestamp without time zone is treated as utc | Good | PASS |
| T32 | Bad messages are rejected: not JSON | Error | PASS |
| T33 | Bad messages are rejected: empty message | Error | PASS |
| T34 | Bad messages are rejected: only spaces | Error | PASS |
| T35 | Bad messages are rejected: unreadable bytes | Error | PASS |
| T36 | Bad messages are rejected: cut-off JSON | Error | PASS |
| T37 | Bad messages are rejected: JSON list instead of object | Error | PASS |
| T38 | Bad messages are rejected: JSON null | Error | PASS |
| T39 | Bad messages are rejected: just a number | Error | PASS |
| T40 | Bad messages are rejected: no heart_rate | Error | PASS |
| T41 | Bad messages are rejected: no customer_id | Error | PASS |
| T42 | Bad messages are rejected: no timestamp | Error | PASS |
| T43 | Bad messages are rejected: empty object | Error | PASS |
| T44 | Bad messages are rejected: customer_id is null | Error | PASS |
| T45 | Bad messages are rejected: customer_id is a number | Error | PASS |
| T46 | Bad messages are rejected: customer_id is empty | Error | PASS |
| T47 | Bad messages are rejected: customer_id too long | Error | PASS |
| T48 | Bad messages are rejected: timestamp is a word | Error | PASS |
| T49 | Bad messages are rejected: impossible date | Error | PASS |
| T50 | Bad messages are rejected: timestamp is a number | Error | PASS |
| T51 | Bad messages are rejected: timestamp 1 hour in future | Error | PASS |
| T52 | Bad messages are rejected: heart_rate is text | Error | PASS |
| T53 | Bad messages are rejected: heart_rate is true/false | Error | PASS |
| T54 | Bad messages are rejected: heart_rate is a list | Error | PASS |
| T55 | Bad messages are rejected: heart_rate is NaN | Error | PASS |
| T56 | Bad messages are rejected: heart_rate 0 | Error | PASS |
| T57 | Bad messages are rejected: heart_rate negative | Error | PASS |
| T58 | Bad messages are rejected: just below possible (24) | Error | PASS |
| T59 | Bad messages are rejected: just above possible (231) | Error | PASS |
| T60 | Bad messages are rejected: 230.6 rounds to 231 | Error | PASS |
| T61 | Bad messages are rejected: heart_rate 300 | Error | PASS |

### Health alert rules ([episodes.py](pulseguard/processing/episodes.py))  ([`tests/test_episodes.py`](tests/test_episodes.py))

| # | Test case | Type | Result |
|---|---|---|---|
| T62 | Normal readings never alert | Good | PASS |
| T63 | Alert opens after 30 seconds out of range | Good | PASS |
| T64 | Alert opens only once then closes when normal | Good | PASS |
| T65 | Critical when far above the limit | Good | PASS |
| T66 | Low episode | Good | PASS |
| T67 | Patients are tracked separately | Good | PASS |
| T68 | Ongoing alert reports its latest peak | Good | PASS |
| T69 | Episode id is the same if readings are replayed | Good | PASS |
| T70 | Short spike is not an alert | Error | PASS |
| T71 | Spike that dips back to normal restarts the count | Error | PASS |
| T72 | Switching from high to low closes and starts again | Error | PASS |
| T73 | Readings with gaps still count by time | Error | PASS |

### Consumer ([consumer.py](pulseguard/services/consumer.py), [batch.py](pulseguard/processing/batch.py))  ([`tests/test_consumer.py`](tests/test_consumer.py))

| # | Test case | Type | Result |
|---|---|---|---|
| T74 | Sort messages | Good | PASS |
| T75 | Full flow into database | Good | PASS |
| T76 | Timing is measured | Good | PASS |
| T77 | Timing text with no messages | Good | PASS |
| T78 | Empty poll does nothing | Error | PASS |
| T79 | Batch of only bad messages | Error | PASS |
| T80 | Reading the same messages twice saves them once | Error | PASS |
| T81 | Nothing is committed if the database fails | Error | PASS |
| T82 | Database fails then recovers | Error | PASS |
| T83 | Consumer gives up if kafka is down | Error | PASS |

### Database ([database.py](pulseguard/storage/database.py), [alerts_db.py](pulseguard/storage/alerts_db.py) + schema rules)  ([`tests/test_database.py`](tests/test_database.py))

| # | Test case | Type | Result |
|---|---|---|---|
| T84 | Save good and rejected | Good | PASS |
| T85 | Duplicate is skipped not an error | Good | PASS |
| T86 | Database works out seconds per step | Good | PASS |
| T87 | Reading without timing still saves | Good | PASS |
| T88 | Timing per minute view | Good | PASS |
| T89 | Database refuses bad rows: heart rate above 230 | Error | PASS |
| T90 | Database refuses bad rows: heart rate 0 | Error | PASS |
| T91 | Database refuses bad rows: status not normal/low/high | Error | PASS |
| T92 | Database refuses bad rows: no customer id | Error | PASS |
| T93 | Database refuses bad rows: no timestamp | Error | PASS |
| T94 | Database refuses bad rows: customer id too long | Error | PASS |
| T95 | One bad row cancels the whole batch | Error | PASS |
| T96 | Connection still works after a failed batch | Error | PASS |
| T97 | Connect gives up if database is down | Error | PASS |

### Database outage while running: wait and retry the same batch  ([`tests/test_retry.py`](tests/test_retry.py))

| # | Test case | Type | Result |
|---|---|---|---|
| T98 | Same batch is saved once the database is back | Good | PASS |
| T99 | Consumer keeps running through a database outage | Good | PASS |
| T100 | Alert service keeps running through a database outage | Good | PASS |
| T101 | A bug is not retried | Error | PASS |
| T102 | A row the database refuses is not retried | Error | PASS |
| T103 | Messages handed out while paused are put back | Error | PASS |
| T104 | Patient limits reload during an outage does not crash | Error | PASS |

### Health alerts end to end: consumer, alerts topic, alert service, real email server  ([`tests/test_alerts.py`](tests/test_alerts.py), [`tests/test_alert_emails.py`](tests/test_alert_emails.py))

| # | Test case | Type | Result |
|---|---|---|---|
| T105 | Personal limits decide the status | Good | PASS |
| T106 | Sustained high heart rate creates one alert | Good | PASS |
| T107 | Open alert survives a consumer restart | Good | PASS |
| T108 | Alert service emails once and then resolved | Good | PASS |
| T109 | Alert message triggers email and is committed | Good | PASS |
| T110 | Short spike creates no alert and no email | Error | PASS |
| T111 | Replayed kafka messages do not send a second email | Error | PASS |
| T112 | Replayed readings do not create a second alert | Error | PASS |
| T113 | Email server down then back alert is not lost | Error | PASS |
| T114 | Alert service failure sends failure email | Error | PASS |

### System problem and back-online emails ([system_alerts.py](pulseguard/notifications/system_alerts.py), [back_online.py](pulseguard/notifications/back_online.py)), sent to a real local email server  ([`tests/test_email.py`](tests/test_email.py), [`tests/test_failure_emails.py`](tests/test_failure_emails.py), [`tests/test_back_online.py`](tests/test_back_online.py), [`tests/test_self_check_report.py`](tests/test_self_check_report.py))

| # | Test case | Type | Result |
|---|---|---|---|
| T115 | Email is really sent | Good | PASS |
| T116 | System problem email is written in plain words | Good | PASS |
| T117 | Subject says what stopped and why: consumer, Kafka down | Good | PASS |
| T118 | Subject says what stopped and why: alert service, database down | Good | PASS |
| T119 | Subject says what stopped and why: producer, a bug | Good | PASS |
| T120 | Ctrl c does not send an email | Good | PASS |
| T121 | Email when consumer cannot reach the database | Error | PASS |
| T122 | Email when consumer cannot reach kafka | Error | PASS |
| T123 | Email when producer cannot reach kafka | Error | PASS |
| T124 | Email when pipeline check fails | Error | PASS |
| T125 | Email server down does not crash | Error | PASS |
| T126 | No email when turned off | Error | PASS |
| T127 | Back online email after a failure | Good | PASS |
| T128 | Back online is sent only once | Good | PASS |
| T129 | Normal start sends no back online email | Good | PASS |
| T130 | Downtime counts from the first failure | Good | PASS |
| T131 | Downtime is easy to read: 42-42 s | Good | PASS |
| T132 | Downtime is easy to read: 75-1 min 15 s | Good | PASS |
| T133 | Downtime is easy to read: 4000-1 h 6 min | Good | PASS |
| T134 | Consumer down then restarted sends both emails | Good | PASS |
| T135 | Back online is kept if email cannot be sent | Error | PASS |
| T136 | Damaged state file still sends back online | Error | PASS |
| T137 | Self check all working | Good | PASS |
| T138 | Self check only alert emails broken | Good | PASS |
| T139 | Self check something else broken | Good | PASS |

## End-to-end test cases ([`check_pipeline.py`](scripts/check_pipeline.py))

Run with Docker, [`consumer.py`](pulseguard/services/consumer.py) and [`alert_service.py`](pulseguard/services/alert_service.py) running: `python -m scripts.check_pipeline`. The last two checks send heart-rate stories: 20 seconds at 150 bpm (should **not** alert), and 35 seconds at 150 bpm (should alert **and** be emailed). Test patients are not registered, so the clinic default limits (50–120) apply.

| # | Test case | Type | Expected | Result |
|---|---|---|---|---|
| E01 | resting heart rate | Good | `normal` | PASS |
| E02 | exercising, still ok | Good | `normal` | PASS |
| E03 | exactly 50 | Good | `normal` | PASS |
| E04 | exactly 120 | Good | `normal` | PASS |
| E05 | too low | Good | `low` | PASS |
| E06 | too high | Good | `high` | PASS |
| E07 | sensor says 0 | Error | `rejected:impossible_heart_rate` | PASS |
| E08 | sensor says 300 | Error | `rejected:impossible_heart_rate` | PASS |
| E09 | negative heart rate | Error | `rejected:impossible_heart_rate` | PASS |
| E10 | heart rate is text | Error | `rejected:heart_rate_not_a_number` | PASS |
| E11 | missing heart rate | Error | `rejected:missing_heart_rate` | PASS |
| E12 | missing customer id | Error | `rejected:missing_customer_id` | PASS |
| E13 | bad timestamp | Error | `rejected:invalid_timestamp` | PASS |
| E14 | timestamp in future | Error | `rejected:future_timestamp` | PASS |
| E15 | broken JSON | Error | `rejected:invalid_json` | PASS |
| E16 | JSON list, not object | Error | `rejected:invalid_json` | PASS |
| E17 | same reading twice | Error | `duplicate` | PASS |
| E18 | 20 s spike | Error | `no alert` | PASS |
| E19 | 35 s racing heart | Good | `alert:high:emailed` | PASS |

### Seeing a failed check

Stop the consumer and run `python -m scripts.check_pipeline`. After 30 seconds the checks show **FAIL** (only `20 s spike / no alert` passes, because nothing was saved), and a `[PulseGuard] SYSTEM PROBLEM: self-check failed` email lists them. Start the consumer again and the waiting messages are processed: the next run passes.

Run it yourself against the real Kafka and paste your own results here for your report.
