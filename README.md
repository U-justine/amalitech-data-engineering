# Real-Time E-commerce Data Ingestion — Spark Structured Streaming → PostgreSQL

This project simulates e-commerce user events (views, add-to-carts, purchases) as CSV files. Spark Structured Streaming picks them up as they arrive, cleans and validates them, and stores them in PostgreSQL within a few seconds.

![Architecture](system_architecture.png)

## Deliverables (all in this folder)

| File | Description |
|---|---|
| `data_generator.py` | Python script to generate CSV event data |
| `spark_streaming_to_postgres.py` | Spark Structured Streaming job to process and write data |
| `postgres_setup.sql` | SQL script to create the database and tables |
| `postgres_connection_details.txt` | Host, port, database, user and password |
| `project_overview.md` | System components and data flow |
| `user_guide.md` | Step-by-step instructions to run the project |
| `test_cases.md` | Manual test plan with expected vs actual outcomes |
| `performance_metrics.md` | Latency, throughput and other performance data |
| `system_architecture.png` | Diagram of data flow and components |

Supporting files: `requirements.txt` (Python packages) and `run_benchmark.py` (re-runs the performance tests). The `data/` and `logs/` folders are created automatically when you run the project.

## Quick start (inside WSL / Linux, from this folder)

```bash
sudo service postgresql start
source ~/venvs/ecom/bin/activate

python spark_streaming_to_postgres.py      # terminal 1: wait for "query started"
python data_generator.py                   # terminal 2

PGPASSWORD=spark_pass psql -h localhost -U spark_user -d ecommerce_stream -c "SELECT * FROM v_event_summary;"
```

For first-time installation, see **[user_guide.md](user_guide.md)**.
