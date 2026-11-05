# Performance Metrics Report

## 1. Test setup

| Item | Value |
|---|---|
| Hardware | 2 vCPU, 7 GB RAM (Linux VM). Spark, PostgreSQL and the generator all ran on this one machine. |
| Software | PySpark 3.5.3 in `local[*]` mode · OpenJDK 21 · PostgreSQL 16.15 · JDBC 42.7.2 |
| Spark settings | `shuffle.partitions=4`, JDBC `batchsize=5000`, `reWriteBatchedInserts=true` |
| Method | `python run_benchmark.py`. For each scenario the tables, input folder and checkpoint are reset, Spark is started, the generator runs at a fixed rate, and the script waits until every row is in PostgreSQL. Raw output is in `logs/benchmark_results.json`. |
| Data | Clean events (`--dirty-rate 0`), seed 2026 |

### Metric definitions

- **End-to-end (E2E) latency:** `inserted_at − event_timestamp`, the time from when the generator created the event to when the row was committed in PostgreSQL. It includes file batching, waiting for the next trigger, Spark processing and the database write.
- **Steady-state latency:** E2E latency excluding batches 0 and 1. Those first two batches carry one-off JVM/JDBC warm-up and the files that queued up while Spark was starting.
- **Batch duration:** time from the start of `foreachBatch` to the commit of the batch metrics row.
- **PG write time:** the part of the batch spent writing to PostgreSQL (staging load, upsert, rejects).
- **Sustained throughput:** rows stored ÷ (last batch finished − first batch started).
- **Spark processed rows/s:** Spark's own `processedRowsPerSecond`, the processing speed while a batch is actually running.

## 2. Results

### 2.1 Completeness

| Scenario | Rows generated | Rows in PostgreSQL | Loss | Duplicates |
|---|---:|---:|---:|---:|
| S1 · 100 ev/s, 5 s trigger | 6,000 | 6,000 | 0 | 0 |
| S2 · 1,000 ev/s, 5 s trigger | 60,000 | 60,000 | 0 | 0 |
| S3 · 1,000 ev/s, 2 s trigger | 60,000 | 60,000 | 0 | 0 |
| S4 · ~4,350 ev/s, 5 s trigger | 300,000 | 300,000 | 0 | 0 |
| B1 · 200-file backlog | 200,000 | 200,000 | 0 | 0 |
| **Total** | **626,000** | **626,000** | **0** | **0** |

### 2.2 Latency (milliseconds)

| Scenario | Trigger | Steady p50 | Steady p95 | Steady max | Overall p50 | Overall p95 | Overall max |
|---|---:|---:|---:|---:|---:|---:|---:|
| S1 · 100 ev/s | 5 s | **3,515** | 5,705 | 5,861 | 3,742 | 8,414 | 9,656 |
| S2 · 1,000 ev/s | 5 s | **3,919** | 6,102 | 6,621 | 4,465 | 9,597 | 11,612 |
| S3 · 1,000 ev/s | 2 s | **2,016** | 3,217 | 4,660 | 2,149 | 6,810 | 8,904 |
| S4 · ~4,350 ev/s | 5 s | **4,102** | 6,683 | 7,025 | 4,621 | 11,432 | 13,266 |
| B1 · backlog | as fast as possible | n/a | n/a | n/a | 28,289* | 34,019* | 34,181* |

\* In B1 all 200,000 events existed before Spark started. Its latency mostly measures queue time, not pipeline speed.

### 2.3 Throughput and batch behaviour

| Scenario | Batches | Avg rows/batch | Avg batch duration | Avg PG write | Max PG write | Spark rows/s (avg / peak) | Sustained rows/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| S1 | 13 | 462 | 1,431 ms | 369 ms | 1,904 ms | 345 / 560 | 102 |
| S2 | 13 | 4,615 | 1,659 ms | 460 ms | 1,714 ms | 2,769 / 3,906 | 1,013 |
| S3 | 30 | 2,000 | 1,141 ms | 298 ms | 1,546 ms | 1,588 / 2,404 | 982 |
| S4 | 14 | 21,429 | 2,492 ms | 839 ms | 2,310 ms | 8,432 / 11,755 | 4,612 |
| B1 | 4 | 50,000 | 5,331 ms | 2,026 ms | 3,616 ms | 9,121 / 12,373 | **8,304** |

The maximum PG write times (about 1.5 to 1.9 s) all come from batch 0, when the JDBC connection and the JVM are warming up. After that, writes take 0.2 to 0.9 s.

### 2.4 Other measurements

| Metric | Value |
|---|---|
| Spark cold start (process start → query running) | about 15 to 20 s |
| First file after start (TC-04) | 7.1 s, including warm-up |
| Single file detected and stored, 2 s trigger | 1.7 s |
| Final drain after the generator stops (S4) | about 2.7 s (the last row was stored 2.7 s after the last file was written) |
| Storage footprint | 200,000 rows = 53 MB including 5 indexes (about 280 bytes/row) |
| Recovery after a PostgreSQL outage | Restart processed 1,500 missed rows in one batch with 0 loss and 0 duplicates (TC-13) |

## 3. Analysis

1. **The trigger interval sets the latency.** With a 5 s trigger the steady-state median is about 3.5 to 4.1 s, regardless of whether the load is 100 or 4,350 events/s. Cutting the trigger to 2 s brought the median down to **2.0 s** (−49%) and the p95 to 3.2 s at the same load. On average a file waits half a trigger interval before it is picked up, plus about 1 to 2.5 s of processing.
2. **Load has only a small effect on latency.** A 43× increase in load (S1 → S4) raised the steady-state median by only about 0.6 s, because larger batches are processed more efficiently. Spark's per-batch speed went from 345 rows/s to 8,400 rows/s, since the fixed per-batch overhead (about 1 s for planning, the JDBC connection and the upsert) is spread over more rows.
3. **The system has capacity to spare at the highest tested rate.** At about 4,350 events/s an average batch took 2.5 s, half of the 5 s trigger budget, and the pipeline finished 2.7 s after the generator stopped. S4 was limited by the generator (one Python process) rather than by Spark. The backlog test (B1) shows an upper bound of about **8,300 rows/s sustained** (12,400 peak) on 2 vCPUs, so the pipeline should handle roughly 8,000 events/s before batches start taking longer than the trigger interval.
4. **The database write is about 30% of each batch** (839 of 2,492 ms in S4). Bulk-loading into an unlogged staging table and then running one set-based `INSERT … ON CONFLICT` keeps the per-row cost low while still preventing duplicates.
5. **Overall p95 and max latencies are inflated by start-up.** Batches 0 and 1 contain the files that queued while Spark was starting and include JVM warm-up. In a long-running deployment that cost occurs only once.

## 4. Assessment against targets

| Target (assumed for a near-real-time analytics feed) | Result | Met? |
|---|---|---|
| Steady-state p95 E2E latency < 10 s | 3.2 to 6.7 s | ✅ |
| Keep up with ≥ 1,000 events/s without falling behind | Kept up with about 4,350 ev/s; upper bound about 8,300 ev/s | ✅ |
| Average batch duration < trigger interval | 1.1 to 2.5 s vs 2 to 5 s | ✅ |
| Zero data loss / zero duplicates | 626,000 of 626,000 rows, 0 duplicates, including the outage test | ✅ |

## 5. Tuning recommendations

| Goal | Change | Trade-off |
|---|---|---|
| Lower latency | `--trigger-seconds 1` or 2, or continuous file production with smaller files | More, smaller batches; more fixed overhead and more transactions in PostgreSQL |
| Higher throughput | Raise `--max-files-per-trigger`, add cores (`local[*]` / a cluster), raise JDBC `batchsize`, `numPartitions` for parallel JDBC writes | Larger batches mean higher worst-case latency |
| Lower PG write cost at scale | Partition `user_events` by day; drop unused indexes; use `COPY` through a staging file | More operational complexity |
| Sub-second latency | Replace the folder source with Kafka | Extra infrastructure |

## 6. Live results on the developer machine (Windows + WSL2)

These figures come from the project running on the developer's own laptop, with the project folder on the Windows drive. That is a slower path for WSL file access than the benchmark machine. The Spark trigger was the default 5 s.

| Metric | Live value | Benchmark machine (S1/S2, 5 s trigger) |
|---|---|---|
| Median end-to-end latency (event created → row in PostgreSQL) | **4.95 s** (a first, smaller run gave 5.69 s) | 3.5 to 3.9 s steady state, 3.7 to 4.5 s overall |
| Average PostgreSQL write per batch | **586 ms** | 369 to 460 ms |
| Rows processed across the session | 8,000 (7,905 stored, 81 rejected, 14 duplicates) | n/a |
| Data loss | **0**: input = stored + rejected + duplicates | 0 |
| Cold restart with a backlog | 10 queued files (1,000 rows) processed in one batch of **10.4 s** (PostgreSQL write 2,498 ms) | First batch 1.5 to 1.9 s for PostgreSQL write |

**Interpretation:** latency on the laptop is about 1 s higher than on the benchmark machine. That fits the slower WSL access to the Windows drive and the 5 s trigger, and it is well inside the 10 s target. The single slow batch after the restart is a one-off. It combines Spark warm-up with a 10× backlog, and Spark logs it as "falling behind" only for that batch.

## 7. How to reproduce

```bash
python run_benchmark.py               # all scenarios (about 10 minutes; resets tables, input folder and checkpoint)
python run_benchmark.py --only S3     # a single scenario
cat logs/benchmark_results.json
```
