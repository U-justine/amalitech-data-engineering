# Test Plan & Results — Real-Time E-commerce Pipeline

**Test environment:** Linux, 2 vCPU, 7 GB RAM · Python 3.13 · OpenJDK 21 · PySpark 3.5.3 (local[*]) · PostgreSQL 16.15 · JDBC driver 42.7.2  
**Executed:** 3 Nov 2026  
**Result:** 17 of 17 test cases pass, and all 5 live checks pass on the developer machine (section E). TC-07 failed on the first run; the defect was fixed and the test re-run (see the defect log below).

The edge-case input file used in TC-05 to TC-09 is reproduced in the [appendix](#appendix--edge-case-input-file).

---

## A. Data generation (Part 1)

| ID | Test | Steps | Expected | Actual | Status |
|---|---|---|---|---|---|
| TC-01 | CSV files are created correctly | `python data_generator.py --files 3 --events-per-file 50 --interval 0 --seed 1` | 3 files named `events_<ts>_<n>.csv`, each with a header plus 50 rows and 11 columns | 3 files created, 153 lines in total (3 headers + 150 rows). The header lists all 11 columns in the expected order. | ✅ Pass |
| TC-02 | Event content is realistic and unique | Parse the 3 files and count event types and unique IDs | Every `event_id` is unique; mostly views, then carts, then purchases; prices match the catalogue | 150 unique IDs out of 150 rows. view 109 (73%), add_to_cart 30 (20%), purchase 11 (7%). Prices match the catalogue and timestamps are UTC with milliseconds. | ✅ Pass |
| TC-03 | No partially written files are exposed | Inspect `.staging/` and the input folder after the run | Staging folder is empty; only complete files are in the input folder | Staging was empty; every file in the input folder was complete. Spark never logged a malformed or truncated read in any run. | ✅ Pass |

## B. Spark detection and transformation (Part 2)

| ID | Test | Steps | Expected | Actual | Status |
|---|---|---|---|---|---|
| TC-04 | Spark detects new files | Start the job (2 s trigger), copy one file into `data/input/`, and measure the time until the batch metrics row appears | File picked up within one trigger interval plus processing time | First file after start-up: **7.1 s** (includes JVM/JDBC warm-up). Next file: **1.7 s**. In every run each file was processed exactly once. | ✅ Pass |
| TC-05 | Valid rows are cleaned and typed correctly | Stream `edge_cases.csv` (12 rows) | `"  PURCHASE "` → `purchase`; `" Desktop "` → `desktop`; `electronics` → `Electronics`; total = price × qty; ISO `T` timestamp parsed | Row 2222… stored as `purchase`, `desktop`, `Electronics`, total **998.00** (499.00 × 2). Row aaaa… with `2026-11-03T08:00:10` parsed correctly, total 237.00 (79.00 × 3). Milliseconds kept (`08:00:01.5`). | ✅ Pass |
| TC-06 | Invalid rows are rejected with the right reason | Same file; query `rejected_events` | 8 rejections, one per defect type | negative price · missing user_id · invalid event_type (`click??`) · quantity not integer (`abc`) · unparseable event_timestamp · non-positive quantity (0) · incomplete row (missing columns) · invalid event_id (`not-a-uuid`). All 8 matched. | ✅ Pass |
| TC-07 | Timestamps are stored without shifting | Compare stored `event_timestamp` with the CSV value | `2026-11-03 08:00:00` is stored as `08:00:00` | **Run 1: FAIL.** Stored as `10:00:00` (+2 h, the host's UTC offset). **Run 2 (after fix D-1): PASS**, stored as `08:00:00`. | ✅ Pass (after fix) |
| TC-08 | Duplicate inside one batch | `edge_cases.csv` contains event 1111… twice | Stored once and counted as a duplicate | 3 rows inserted, `duplicate_rows = 1`. Reconciles: 12 = 3 valid + 8 rejected + 1 duplicate. | ✅ Pass |
| TC-09 | Duplicate across batches (same data, new file name) | Copy `edge_cases.csv` as `edge_cases_copy.csv` | 0 new rows in `user_events` | Batch 1: input 12, inserted **0**, duplicates 4. `user_events` stayed at 3 rows. *Note:* the 8 invalid rows are logged again in `rejected_events`, which is acceptable for an audit log. | ✅ Pass |
| TC-10 | Empty (header-only) file | Copy a CSV that has only the header row | No error and no rows written | No batch was written, no errors, and the stream kept running. | ✅ Pass |
| TC-11 | Same file name written again | Overwrite `edge_cases.csv` in place | Not reprocessed, because Spark tracks files by path | Not reprocessed. This is a documented limitation (see the user guide, Troubleshooting). The generator always uses unique names. | ✅ Pass |

## C. PostgreSQL storage (Part 3)

| ID | Test | Steps | Expected | Actual | Status |
|---|---|---|---|---|---|
| TC-12 | Volume run with dirty data: nothing lost | `--files 15 --events-per-file 500 --interval 1 --dirty-rate 0.05 --seed 7`, then reconcile | input = stored + rejected + duplicates; no stored row breaks a rule | 7,500 = **7,144** stored + **299** rejected + **57** duplicates. 0 rule violations (type, price, quantity, total, case). All 56 rows that only needed case/whitespace fixes were kept (56/56). | ✅ Pass |
| TC-13 | PostgreSQL outage during streaming | Stop PostgreSQL with the job running, generate 3 files, restart PostgreSQL, restart the job | Job stops cleanly with an error and no partial data; after restart the missed files load exactly once | Job terminated with `OperationalError: Connection refused`, and `user_events` was unchanged (7,144). After restart, batch 11 loaded those 3 files (1,500 rows, 0 duplicates). | ✅ Pass |
| TC-14 | Files arriving while Spark is down | With the job stopped, generate 2 files, then restart | Picked up on restart | Batch 12: 2 files, 1,000 rows. Total 9,644 = 7,144 + 2,500. 20 of 20 source files are present in the table. | ✅ Pass |
| TC-15 | Restart with nothing new | Run `--available-now` again | No batches and no duplicates | 0 batches; row count stayed at 9,644. | ✅ Pass |
| TC-16 | Database constraints | Insert directly with `event_type='refund'` and with `price=-1` | Both rejected by CHECK constraints | `violates check constraint "user_events_event_type_check"` and `"user_events_price_check"` | ✅ Pass |
| TC-17 | Setup script is re-runnable | Run `postgres_setup.sql` twice | Second run succeeds with "already exists" notices only | Second run printed only `NOTICE … already exists, skipping`, with no errors. | ✅ Pass |

## D. Performance

Load and latency tests are covered in `performance_metrics.md`. In summary, every scenario stored 100% of the rows, the pipeline kept up with the highest load the generator could produce, and steady-state latency stayed within the trigger interval plus a few seconds.

---

## E. Live verification on the developer machine (5 Nov 2026)

**Environment:** Windows + WSL2 (Ubuntu), VS Code, project folder on the Windows drive (`/mnt/c/...`), PostgreSQL running locally in WSL, Spark job using the default 5 s trigger.

These checks answer the five "What to Test" questions from the project brief directly.

| # | Brief question | Command / evidence | Expected | Actual (live) | Status |
|---|---|---|---|---|---|
| L-1 | Are the CSV files being generated correctly? | `python data_generator.py --files 10 --dirty-rate 0.05`, then `head -3` on the newest file | 10 files with an 11-column header and valid rows | 10 files (`events_20261105_085959…` to `…090017…`), 1,000 events. Header and sample rows are correct, e.g. `purchase, Bluetooth Speaker, 39.50, 3, mobile, 2026-11-05 09:00:17.285` | ✅ Pass |
| L-2 | Is Spark detecting and processing new files? | Spark was stopped while the files were written, then restarted | Waiting files are picked up automatically on restart, with no regeneration | `[batch 30] files=10 input=1000 valid=950 rejected=44 inserted=950 duplicates_skipped=6`. All 10 files were detected and processed in the first batch after the restart. | ✅ Pass |
| L-3 | Are the data transformations correct? | `SELECT reject_reason, count(*) FROM rejected_events …` and the wrong-totals check query | Bad rows rejected with the correct reason; no stored row breaks a rule | 81 rejections in total: unparseable event_timestamp 29, negative price 16, invalid event_type 15, missing user_id 11, quantity not integer 10. `wrong_totals = 0` (every `total_amount = price × quantity` and every event type is valid). | ✅ Pass |
| L-4 | Is data being written into PostgreSQL without errors? | `SELECT sum(input_rows), sum(inserted_rows), sum(rejected_rows), sum(duplicate_rows) FROM pipeline_batch_metrics` | input = stored + rejected + duplicates | **8,000 = 7,905 + 81 + 14.** Every row is accounted for, and the Spark UI showed no failed jobs. | ✅ Pass |
| L-5 | Are performance metrics within expected limits? | Median of `inserted_at − event_timestamp`; average `write_duration_ms` | Median end-to-end latency under 10 s | Median latency **4.95 s**, average PostgreSQL write **586 ms** per batch | ✅ Pass |

**Observation:** batch 30 logged `Current batch is falling behind … spent 10449 ms` against the 5 s trigger. This is expected. It was the first batch after a restart, carried 10 queued files (10× a normal batch), and included the one-off JVM/JDBC warm-up (the PostgreSQL write took 2,498 ms). Later batches finish within the trigger interval.

---

## Defect log

| ID | Found in | Description | Root cause | Fix | Retest |
|---|---|---|---|---|---|
| D-1 | TC-07 | Stored timestamps were 2 hours later than the CSV value | The session timezone was UTC, but the JDBC driver converts `TIMESTAMP` values using the **JVM default timezone** (host = UTC+2) | Added `spark.driver/executor.extraJavaOptions = -Duser.timezone=UTC` | Pass |
| D-2 | TC-06 | A truncated row (missing trailing columns) was rejected as "price not numeric", which is misleading | No explicit completeness check | Added an "incomplete row (missing columns)" rule before the type checks | Pass |
| D-3 | TC-04 | The batch log line was hidden behind Spark's console progress bar | Progress bar enabled by default | Set `spark.ui.showConsoleProgress=false` | Pass |

---

## Appendix — edge-case input file

```csv
event_id,user_id,session_id,event_type,product_id,product_name,category,price,quantity,device,event_timestamp
11111111-1111-4111-8111-111111111111,U00001,s1,view,P0001,Wireless Earbuds,Electronics,59.99,1,mobile,2026-11-03 08:00:00.000
22222222-2222-4222-8222-222222222222,U00002,s2,  PURCHASE ,P0002,Smartphone,electronics,499.00,2, Desktop ,2026-11-03 08:00:01.500
33333333-3333-4333-8333-333333333333,U00003,s3,purchase,P0003,USB-C Charger,Electronics,-5.00,1,mobile,2026-11-03 08:00:02.000
44444444-4444-4444-8444-444444444444,,s4,view,P0004,Bluetooth Speaker,Electronics,39.50,1,mobile,2026-11-03 08:00:03.000
55555555-5555-4555-8555-555555555555,U00005,s5,click??,P0005,Laptop Stand,Electronics,29.95,1,mobile,2026-11-03 08:00:04.000
66666666-6666-4666-8666-666666666666,U00006,s6,add_to_cart,P0006,Running Shoes,Fashion,89.90,abc,tablet,2026-11-03 08:00:05.000
77777777-7777-4777-8777-777777777777,U00007,s7,view,P0007,Denim Jacket,Fashion,74.00,1,mobile,not-a-timestamp
88888888-8888-4888-8888-888888888888,U00008,s8,add_to_cart,P0008,Cotton T-Shirt,Fashion,14.99,0,mobile,2026-11-03 08:00:07.000
not-a-uuid,U00009,s9,view,P0009,Leather Belt,Fashion,24.50,1,mobile,2026-11-03 08:00:08.000
11111111-1111-4111-8111-111111111111,U00001,s1,view,P0001,Wireless Earbuds,Electronics,59.99,1,mobile,2026-11-03 08:00:00.000
99999999-9999-4999-8999-999999999999,U00010,s10,view,P0010
aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa,U00011,s11,add_to_cart,P0011,Coffee Maker,Home & Kitchen,79.00,3,desktop,2026-11-03T08:00:10
```
