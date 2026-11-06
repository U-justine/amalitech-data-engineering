# Test Plan and Results: Real-Time E-commerce Pipeline

This document lists every test I ran on the pipeline, what I expected to happen, and what actually happened.

**Where and when:** all tests were run on my own laptop (Windows, with Ubuntu on WSL 2) on 6 November 2026. I started from an empty database, with no data files and no Spark checkpoint.

**Software:** PySpark 3.5.3, Python 3.14, OpenJDK 17 and PostgreSQL, all running in Ubuntu.

**Result: all 17 tests passed.**

The tests follow the five questions in the project brief:

| Question from the brief | Tests |
|---|---|
| Are the CSV files being generated correctly? | TC-01 to TC-03 |
| Is Spark detecting and processing new files? | TC-04, TC-10, TC-11 |
| Are the data transformations correct? | TC-05 to TC-09, TC-12 |
| Is data being written into PostgreSQL without errors? | TC-12 to TC-17 |
| Are performance metrics within expected limits? | TC-18, and [performance_metrics.md](performance_metrics.md) |

---

## A. Generating the data

| Test | What I checked | How | Expected | What happened | Result |
|---|---|---|---|---|---|
| TC-01 | The generator creates correct CSV files | `python data_generator.py --output-dir test_data/gen_check --files 3 --events-per-file 50 --interval 0 --seed 1`, then `wc -l` | 3 files, each with the 11-column header and 50 rows | 3 files, 51 lines each (header + 50 rows), **153 lines in total**. The header has all 11 columns in the right order. | Pass |
| TC-02 | Events are unique and realistic | Counted IDs and event types with a short Python command | Every event ID is different; mostly views, fewer carts and purchases | **150 rows, 150 unique IDs.** 109 views (73%), 30 add-to-carts (20%), 11 purchases (7%). | Pass |
| TC-03 | No half-written files are left behind | `ls -A test_data/.staging` | The waiting folder is empty | The command printed **nothing**: the folder was empty. Every file was moved in complete. | Pass |

---

## B. Spark picking up and cleaning the data

For these tests, Spark was running in one terminal (`python spark_streaming_to_postgres.py`) while I sent files from a second terminal.

| Test | What I checked | How | Expected | What happened | Result |
|---|---|---|---|---|---|
| TC-04 | Spark notices new files and processes them | Ran `python data_generator.py` (20 files of 100 events) | Every file is picked up and saved | Batches 0 to 8 handled **20 files and 2,000 rows**, with 0 rejected and 0 duplicates. The database summary showed 382 add-to-carts + 191 purchases + 1,427 views = **2,000**. | Pass |
| TC-05 | Messy but valid values are tidied up and kept | Copied [`test_data/edge_cases.csv`](test_data/edge_cases.csv) into `data/input` | `"  PURCHASE "` becomes `purchase`, `electronics` becomes `Electronics`, `" Desktop "` becomes `desktop`; total = price x quantity | Event `2222…` was saved as `purchase`, `Electronics`, `desktop`, total **998.00** (499.00 x 2). Event `aaaa…`, whose time was written in a different format (`2026-11-03T08:00:10`), was read correctly, total **237.00** (79.00 x 3). | Pass |
| TC-06 | Broken rows are rejected with the right reason | Same file; checked `rejected_events` | 8 rows rejected, each with its own reason | All 8 rejected with the right reason: negative price, missing user_id, invalid event_type (`click??`), quantity not integer (`abc`), unparseable event_timestamp, non-positive quantity (0), incomplete row (missing columns), invalid event_id (`not-a-uuid`). | Pass |
| TC-07 | Times are stored without shifting | Compared the stored times with the file | `08:00:00` in the file is stored as `08:00:00` | All times were stored as **08:00:xx**, even though my laptop is on UTC+2. Milliseconds were kept (`08:00:01.5`). | Pass |
| TC-08 | A duplicate inside one file is saved once | Event `1111…` appears twice in the test file | Saved once, counted as a duplicate | `[batch 14] input=12 valid=3 rejected=8 inserted=3 duplicates_skipped=1`. 12 rows = 3 saved + 8 rejected + 1 duplicate. | Pass |
| TC-09 | The same data sent again under a new file name is not saved twice | `cp test_data/edge_cases.csv data/input/edge_cases_copy.csv` | 0 new events saved | `[batch 15] input=12 valid=3 rejected=8 inserted=0 duplicates_skipped=4`. **Nothing new was saved.** | Pass |
| TC-10 | An empty file (header only) causes no problem | `cp test_data/header_only.csv data/input/` | No batch and no error | No new batch line, no error, and Spark kept running. | Pass |
| TC-11 | A file with a name Spark has already seen is ignored | Copied `edge_cases.csv` into the folder again under the same name | Not processed again | No new batch line. The total stayed at **2,960**. | Pass |

---

## C. Saving to PostgreSQL

| Test | What I checked | How | Expected | What happened | Result |
|---|---|---|---|---|---|
| TC-12 | A run with broken rows: nothing is lost and nothing bad is saved | `python data_generator.py --files 10 --dirty-rate 0.05` (1,000 events, about 5% broken on purpose) | Every row ends up somewhere; no saved row breaks a rule | Batches 9 to 13 handled the 1,000 rows. Across the run so far: **3,000 in = 2,957 saved + 33 rejected + 10 duplicates.** Reasons: quantity not integer 11, invalid event_type 7, negative price 6, missing user_id 5, unparseable timestamp 4. The rule check found **0** saved rows with a wrong type, price, quantity or total. | Pass |
| TC-13 | The database is switched off while Spark is running | `sudo service postgresql stop`, then sent 3 files (1,500 events) | Spark stops with a clear error instead of losing data | Spark stopped with `psycopg2.OperationalError: connection to server at "localhost" ... port 5432 failed: Connection refused`. After switching the database back on, the count was still **2,960**: nothing was half-saved. | Pass |
| TC-14 | Files that arrive while things are down are handled after a restart | Switched the database on, sent 2 more files (1,000 events) while Spark was stopped, then ran `python spark_streaming_to_postgres.py --available-now` | All 5 waiting files are saved once | Count went from 2,960 to **5,460** (+2,500): all 5 files saved, none lost and none twice. | Pass |
| TC-15 | Restarting with nothing new does not process anything again | Ran `--available-now` once more | No batches; count unchanged | No batch lines. The Spark web page showed only "Executor driver added" and no jobs. Count stayed at **5,460**. | Pass |
| TC-16 | The database itself refuses bad data | Tried to insert a `refund` event and a price of -1 directly with SQL | Both refused | `violates check constraint "user_events_event_type_check"` and `violates check constraint "user_events_price_check"`. | Pass |
| TC-17 | The setup script can safely be run again | `sudo -u postgres psql < postgres_setup.sql` | Runs without errors and changes nothing | Only `NOTICE: relation ... already exists, skipping` messages, and no errors. | Pass |

---

## D. Speed

| Test | What I checked | How | Expected | What happened | Result |
|---|---|---|---|---|---|
| TC-18 | Events reach the database quickly | Measured the time between each event being created and being saved | Typical time well under 10 seconds | Typical time **4.45 seconds**. The slowest event took 10.92 seconds; it was in the very first batch, while Spark was still warming up (that batch took 8.4 seconds). | Pass |

The full speed and load tests (up to about 3,900 events per second and 626,000 events in total) are in [performance_metrics.md](performance_metrics.md).

---

## Things I noticed during testing

- **The first batch is always slow.** Spark printed `Current batch is falling behind` once, for batch 0, because Spark and the database connection were still starting up. All later batches finished quickly (database writes of 0.2 to 0.5 seconds).
- **Listing the folder on the Windows drive is slow.** Spark printed `Listed 33 file(s) in 2702 ms`. Ubuntu on WSL reads folders on the Windows Desktop slowly, so moving the project into Ubuntu's own home folder would make each round faster.
- **Rejected rows are logged again if the same data is sent again.** In TC-09, the 8 broken rows from the copied file were added to `rejected_events` a second time. That is acceptable: it is a log of what arrived, and the good events were not saved twice.

---

## Problems found and fixed during development

| Problem | Cause | Fix | Checked again |
|---|---|---|---|
| Times were stored 2 hours late | Spark used UTC, but the database driver converted times using the computer's own time zone (UTC+2) | Set Java to UTC as well (`-Duser.timezone=UTC`) | TC-07: times now stored correctly |
| A cut-off row was rejected with a misleading reason ("price not numeric") | There was no check for missing columns | Added the "incomplete row (missing columns)" check before the other checks | TC-06: now shows the right reason |
| The batch summary line was hidden by Spark's progress bar | Spark shows a progress bar by default | Turned the progress bar off | Batch lines now show clearly |

---

## The test file

[`test_data/edge_cases.csv`](test_data/edge_cases.csv) has 12 rows. Each one tests something specific:

| Row (event ID) | What is special about it | Expected outcome |
|---|---|---|
| 1111… | Normal row | Saved |
| 2222… | Messy text: `"  PURCHASE "`, `electronics`, `" Desktop "` | Tidied up and saved |
| 3333… | Price -5.00 | Rejected: negative price |
| 4444… | No user | Rejected: missing user_id |
| 5555… | Event type `click??` | Rejected: invalid event_type |
| 6666… | Quantity `abc` | Rejected: quantity not integer |
| 7777… | Date `not-a-timestamp` | Rejected: unparseable event_timestamp |
| 8888… | Quantity 0 | Rejected: non-positive quantity |
| not-a-uuid | Bad event ID | Rejected: invalid event_id |
| 1111… (again) | Exact copy of the first row | Skipped as a duplicate |
| 9999… | Row cut off after 5 columns | Rejected: incomplete row |
| aaaa… | Time written as `2026-11-03T08:00:10` | Read correctly and saved |

[`test_data/header_only.csv`](test_data/header_only.csv) contains only the header line, with no data.
