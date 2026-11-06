#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time

import psycopg2

HERE = os.path.dirname(os.path.abspath(__file__))   # project folder
ROOT = HERE
sys.path.insert(0, HERE)
from spark_streaming_to_postgres import load_pg_config  # noqa: E402

DATA = os.path.join(ROOT, "data")
LOGS = os.path.join(ROOT, "logs")
PY = sys.executable

# id, description, files, events/file, interval (s), trigger (s), maxFilesPerTrigger, mode
SCENARIOS = [
    ("S1", "Low load: 100 events/s",        60,  100, 1.0, 5, 10, "stream"),
    ("S2", "Medium load: 1,000 events/s",   60, 1000, 1.0, 5, 10, "stream"),
    ("S3", "Medium load, 2s trigger",       60, 1000, 1.0, 2, 10, "stream"),
    ("S4", "High load: 5,000 events/s",    120, 2500, 0.5, 5, 20, "stream"),
    ("B1", "Backlog: 200 files x 1,000",   200, 1000, 0.0, 0, 50, "backlog"),
]


# Opens a connection to PostgreSQL using the details in postgres_connection_details.txt.
def pg():
    c = load_pg_config(os.path.join(ROOT, "postgres_connection_details.txt"))
    conn = psycopg2.connect(host=c["PG_HOST"], port=c["PG_PORT"], dbname=c["PG_DATABASE"],
                            user=c["PG_USER"], password=c["PG_PASSWORD"])
    conn.autocommit = True
    return conn


# Empties the tables and deletes data/ so each test scenario starts from zero.
def reset():
    with pg() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE user_events, rejected_events, pipeline_batch_metrics, user_events_staging")
    shutil.rmtree(DATA, ignore_errors=True)
    os.makedirs(LOGS, exist_ok=True)
    prog = os.path.join(LOGS, "streaming_progress.jsonl")
    if os.path.exists(prog):
        os.remove(prog)


# Returns how many events are currently stored in user_events.
def count_rows():
    with pg() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM user_events")
        return cur.fetchone()[0]


# Returns the p-th percentile of a list of numbers (e.g. p=95 gives the 95th percentile).
def pct(values, p):
    values = sorted(values)
    k = (len(values) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(values) - 1)
    return values[f] + (values[c] - values[f]) * (k - f)


# Calculates one scenario's results (latency, throughput, batch times) from the database
# and from Spark's progress log.
def collect(sid, desc, expected, wall_s, extra):
    with pg() as conn, conn.cursor() as cur:
        cur.execute("""SELECT EXTRACT(EPOCH FROM (inserted_at - event_timestamp)) * 1000,
                              EXTRACT(EPOCH FROM (processed_at - event_timestamp)) * 1000
                       FROM user_events""")
        rows = cur.fetchall()
        e2e = [float(r[0]) for r in rows]
        # steady state = ignore the first two batches (JVM/JDBC warm-up + start-up backlog)
        cur.execute("""SELECT EXTRACT(EPOCH FROM (inserted_at - event_timestamp)) * 1000
                       FROM user_events WHERE batch_id >= 2""")
        steady = [float(r[0]) for r in cur.fetchall()]
        spark_lat = [float(r[1]) for r in rows]
        cur.execute("""SELECT count(*), avg(write_duration_ms), max(write_duration_ms),
                              avg(input_rows), max(input_rows),
                              EXTRACT(EPOCH FROM (max(batch_finished_at) - min(batch_started_at))),
                              avg(EXTRACT(EPOCH FROM (batch_finished_at - batch_started_at)) * 1000)
                       FROM pipeline_batch_metrics""")
        nb, avg_w, max_w, avg_rows, max_rows, active_s, avg_batch_ms = cur.fetchone()
    prog = []
    path = os.path.join(LOGS, "streaming_progress.jsonl")
    if os.path.exists(path):
        prog = [json.loads(l) for l in open(path, encoding="utf-8")]
    proc_rates = [p["processedRowsPerSecond"] for p in prog if p.get("processedRowsPerSecond")]
    trig = [p["durationMs"].get("triggerExecution", 0) for p in prog]
    stored = len(e2e)
    res = {
        "id": sid, "scenario": desc, "expected_rows": expected, "stored_rows": stored,
        "batches": nb,
        "avg_rows_per_batch": round(float(avg_rows or 0)), "max_rows_per_batch": max_rows,
        "e2e_latency_ms": {"p50": round(pct(e2e, 50)), "p95": round(pct(e2e, 95)),
                           "p99": round(pct(e2e, 99)), "max": round(max(e2e)),
                           "avg": round(statistics.mean(e2e))} if e2e else None,
        "steady_state_e2e_latency_ms": {"p50": round(pct(steady, 50)), "p95": round(pct(steady, 95)),
                                        "max": round(max(steady))} if steady else None,
        "spark_latency_ms_p50": round(pct(spark_lat, 50)) if spark_lat else None,
        "avg_batch_duration_ms": round(float(avg_batch_ms or 0)),
        "avg_pg_write_ms": round(float(avg_w or 0)), "max_pg_write_ms": max_w,
        "avg_trigger_execution_ms": round(statistics.mean(trig)) if trig else None,
        "spark_processed_rows_per_s_avg": round(statistics.mean(proc_rates)) if proc_rates else None,
        "spark_processed_rows_per_s_max": round(max(proc_rates)) if proc_rates else None,
        "active_processing_window_s": round(float(active_s or 0), 1),
        "sustained_throughput_rows_per_s": round(stored / float(active_s)) if active_s else None,
        "wall_clock_s": round(wall_s, 1),
    }
    res.update(extra)
    return res


# Runs one test scenario: starts Spark, generates the events, waits until all rows are stored,
# then collects the results.
def run(s):
    sid, desc, files, epf, interval, trigger, mfpt, mode = s
    print(f"\n=== {sid}: {desc} ===", flush=True)
    reset()
    expected = files * epf
    spark_cmd = [PY, os.path.join(HERE, "spark_streaming_to_postgres.py"),
                 "--max-files-per-trigger", str(mfpt)]
    gen_cmd = [PY, os.path.join(HERE, "data_generator.py"), "--files", str(files),
               "--events-per-file", str(epf), "--interval", str(interval), "--seed", "2026"]
    log = open(os.path.join(LOGS, f"bench_{sid}_spark.log"), "w")

    gen_s = None
    if mode == "backlog":
        subprocess.run(gen_cmd, check=True, stdout=subprocess.DEVNULL)
        t0 = time.time()
        subprocess.run(spark_cmd + ["--available-now"], check=True, stdout=log, stderr=log)
        wall = time.time() - t0
    else:
        spark = subprocess.Popen(spark_cmd + ["--trigger-seconds", str(trigger)], stdout=log, stderr=log)
        time.sleep(25)                                # JVM + Spark start-up
        t0 = time.time()
        subprocess.run(gen_cmd, check=True, stdout=subprocess.DEVNULL)
        gen_s = time.time() - t0
        deadline = time.time() + 300
        while count_rows() < expected and time.time() < deadline:
            time.sleep(0.5)
        wall = time.time() - t0
        spark.terminate()
        spark.wait(timeout=60)
    log.close()
    gen_rate = round(expected / gen_s) if mode != "backlog" else None
    res = collect(sid, desc, expected, wall,
                  {"trigger_s": trigger, "max_files_per_trigger": mfpt,
                   "target_rate_events_per_s": round(epf / interval) if interval else None,
                   "actual_generator_rate_events_per_s": gen_rate})
    print(json.dumps(res, indent=2), flush=True)
    return res


# Starting point: runs all scenarios (or those chosen with --only) and saves the results to JSON.
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    os.makedirs(LOGS, exist_ok=True)
    out = os.path.join(LOGS, "benchmark_results.json")
    previous = {r["id"]: r for r in json.load(open(out))} if os.path.exists(out) else {}
    for s in SCENARIOS:
        if not args.only or s[0] in args.only:
            previous[s[0]] = run(s)
    with open(out, "w") as f:
        json.dump([previous[s[0]] for s in SCENARIOS if s[0] in previous], f, indent=2)
    print("\nSaved logs/benchmark_results.json")


if __name__ == "__main__":
    main()
