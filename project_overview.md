# Project Overview — Real-Time E-commerce Event Ingestion

## Purpose

This project simulates an e-commerce platform that tracks user activity and loads it into a database in near real time. A Python generator writes CSV files of user events (product views, add-to-carts, purchases). Apache Spark Structured Streaming picks up each new file as it arrives, cleans and validates the rows, and writes them to PostgreSQL. Every step is designed so that data is neither lost nor duplicated, even if Spark or the database goes down.

![System architecture](system_architecture.png)

## Components

| Component | File | Role |
|---|---|---|
| Event generator | `data_generator.py` | Creates realistic fake events and writes them as CSV files into `data/input/`. It writes each file to a hidden staging folder first and then renames it into place, so Spark never reads a half-written file. `--dirty-rate` injects bad rows for testing. |
| Streaming job | `spark_streaming_to_postgres.py` | Watches `data/input/`, cleans and validates each micro-batch, and writes it to PostgreSQL through `foreachBatch`. |
| Database schema | `postgres_setup.sql` | Creates the `spark_user` role, the `ecommerce_stream` database, the tables, the indexes and a summary view. It is safe to re-run. |
| Connection config | `postgres_connection_details.txt` | Host, port, database, user and password. The Spark job reads this file, and environment variables override it. |
| Benchmark | `run_benchmark.py` | Re-creates the load tests in `performance_metrics.md`. |

## Data model

**Input CSV (11 columns):** `event_id, user_id, session_id, event_type, product_id, product_name, category, price, quantity, device, event_timestamp`

**PostgreSQL tables**

- `user_events`: holds the cleaned events. Its primary key is `event_id` (UUID). CHECK constraints enforce valid `event_type`, `price >= 0` and `quantity > 0`. The table also adds `total_amount`, `source_file`, `batch_id`, `processed_at` and `inserted_at`.
- `rejected_events`: keeps the raw values of every row that failed validation, with a `reject_reason`.
- `user_events_staging`: an unlogged landing table that Spark bulk-loads for each batch.
- `pipeline_batch_metrics`: one row per micro-batch with the input, valid, rejected, duplicate and inserted counts and the timings.
- `v_event_summary`: a view of event count, distinct users and amount by event type.

## Data flow

1. **Generate.** The generator writes `events_<timestamp>_<n>.csv` into `data/input/` (by default 100 rows every 2 seconds).
2. **Detect.** Spark's file source lists the folder on each trigger (every 5 seconds by default) and picks up files it has not seen before, up to `maxFilesPerTrigger` per batch.
3. **Read.** All columns are read as strings using an explicit schema. A bad value therefore cannot break the stream, and every cast is done deliberately in the next step.
4. **Clean and transform:**
   - Trim every field, and lower-case `event_type` and `device` (so `"  PURCHASE "` becomes `purchase`).
   - Cast `price` to DECIMAL(10,2), `quantity` to INT and `event_timestamp` to TIMESTAMP (UTC).
   - Validate each row and attach the first reason it fails: invalid UUID, missing user or product, unknown event type, incomplete row, non-numeric or negative price, bad quantity, or unparseable timestamp.
   - Derive `total_amount = price × quantity`, the batch id and `processed_at`.
5. **Write (foreachBatch):**
   - Valid rows are de-duplicated on `event_id` within the batch, bulk-loaded through JDBC into the staging table, and then moved into `user_events` with `INSERT … ON CONFLICT (event_id) DO NOTHING`.
   - Invalid rows go to `rejected_events`.
   - Batch statistics go to `pipeline_batch_metrics`, and Spark's progress events go to `logs/streaming_progress.jsonl`.
6. **Checkpoint.** Spark records in `data/checkpoint/` which files have been committed.

## Reliability design

- **Exactly-once results in the database.** The checkpoint combined with the idempotent upsert means that if a batch is replayed after a crash, it adds no duplicate rows. This was tested by stopping PostgreSQL in the middle of the stream and restarting Spark (see `test_cases.md`, TC-10 and TC-11).
- **No partial-file reads.** The generator renames finished files atomically into the watched folder.
- **Nothing silently dropped.** Every input row ends up in exactly one of three places: `user_events`, `rejected_events`, or the duplicate count in `pipeline_batch_metrics`. Across a 7,500-row dirty run these added up exactly.
- **Timezone-safe.** The Spark session and the JVM are both pinned to UTC, so stored timestamps match the CSV whatever the host's timezone is. Testing found and fixed a +2h shift caused by this.

## Key results (2 vCPU, 7 GB RAM, Spark local mode)

- 626,000 events were streamed across the benchmark runs, with 0 lost and 0 duplicated.
- Steady-state median end-to-end latency (event created → row in PostgreSQL) was about 3.5 to 4.1 s with a 5 s trigger and about 2.0 s with a 2 s trigger. The trigger interval accounts for most of the latency.
- The pipeline kept up with about 4,350 events/s using half of its batch time budget. Backlog catch-up reached about 8,300 rows/s.
- See `performance_metrics.md` for the full figures.

## Possible extensions

- Replace the folder source with Kafka for lower latency and multiple producers.
- Add windowed aggregates, such as revenue per minute per category, to a second table.
- Run the job under a supervisor (systemd, Kubernetes, or Airflow with retries) so it restarts automatically after a database outage.
