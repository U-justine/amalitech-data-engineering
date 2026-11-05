# User Guide — Running the Real-Time E-commerce Pipeline

This guide uses **Windows + WSL2 (Ubuntu) + VS Code**, the setup the project was run and verified on. On Linux or macOS, skip Steps 1 to 3 and run the same commands in a normal terminal.

## Project layout

```
ecommerce-streaming/
├── data_generator.py                # Part 1: creates fake event CSV files
├── spark_streaming_to_postgres.py   # Part 2+3: Spark streaming job -> PostgreSQL
├── postgres_setup.sql               # creates database, user, tables
├── postgres_connection_details.txt  # host, port, database, user, password
├── project_overview.md              # how the system works
├── user_guide.md                    # this file
├── test_cases.md                    # test plan with expected vs actual results
├── performance_metrics.md           # latency / throughput report
├── system_architecture.png          # architecture diagram
├── README.md                        # quick start
├── requirements.txt                 # Python packages
├── run_benchmark.py                 # optional: re-runs the performance tests
├── data/   (created when you run it)  input/ = watched folder, checkpoint/ = Spark progress
└── logs/   (created when you run it)  Spark progress log, benchmark results
```

**Run every command from the `ecommerce-streaming` folder.**

---

## Part A: One-time setup

### Step 1: Install WSL (Ubuntu)
Open PowerShell **as Administrator**, run `wsl --install`, and restart your computer. When Ubuntu opens, create a username and password. The password stays invisible while you type.

### Step 2: Install VS Code
Install VS Code from code.visualstudio.com and add the **WSL** and **Python** extensions (both by Microsoft).

### Step 3: Open the project from Ubuntu
In the Ubuntu terminal (change the path to wherever your folder is):
```bash
cd /mnt/c/Users/User/Desktop/ecommerce-streaming
code .
```
VS Code opens with **WSL: Ubuntu** in the bottom-left corner. Open a terminal with **Ctrl + `**.

### Step 4: Install Java, PostgreSQL and the JDBC driver
```bash
sudo apt update
sudo apt install -y openjdk-17-jdk python3-pip python3-venv postgresql libpostgresql-jdbc-java
java -version
```

### Step 5: Create the Python environment
```bash
python3 -m venv ~/venvs/ecom
source ~/venvs/ecom/bin/activate
pip install -r requirements.txt
```
The prompt now starts with `(ecom)`.

### Step 6: Create the database
```bash
sudo service postgresql start
sudo -u postgres psql < postgres_setup.sql
sudo -u postgres psql -c "ALTER ROLE spark_user WITH PASSWORD 'spark_pass';"
```
Check that it worked:
```bash
PGPASSWORD=spark_pass psql -h localhost -U spark_user -d ecommerce_stream -c "\dt"
```
You should see 4 tables: `pipeline_batch_metrics`, `rejected_events`, `user_events` and `user_events_staging`.

---

## Part B: Running the pipeline (every time)

### 1. Start the database
```bash
sudo service postgresql start
```

### 2. Start Spark (left terminal pane)
```bash
source ~/venvs/ecom/bin/activate
python spark_streaming_to_postgres.py
```
Wait until you see `[stream] query started`. Leave it running.

### 3. Generate events (right terminal pane)
Split the terminal with the split icon, then:
```bash
source ~/venvs/ecom/bin/activate
python data_generator.py
```
The Spark pane prints a line for each batch:
```
[batch 3] files=2 input=200 valid=193 rejected=5 inserted=193 duplicates_skipped=2 pg_write=310ms
```

### 4. Check the data
```bash
PGPASSWORD=spark_pass psql -h localhost -U spark_user -d ecommerce_stream -c "SELECT * FROM v_event_summary;"
```

### 5. Stop
Click the Spark pane and press **Ctrl + C**. The next time you start it, it carries on from where it stopped.

---

## Options

| `spark_streaming_to_postgres.py` | Default | Meaning |
|---|---|---|
| `--trigger-seconds` | 5 | How often Spark checks for new files. Lower values give lower latency. |
| `--max-files-per-trigger` | 10 | Maximum number of files per batch |
| `--available-now` | off | Process every file currently waiting, then exit |
| `--run-seconds` | 0 | Stop automatically after N seconds |
| `--jdbc-jar` | auto | Driver path. The job finds `jars/` or `/usr/share/java/postgresql.jar` on its own. |
| `--input-dir`, `--checkpoint-dir` | `data/input`, `data/checkpoint` | Folder locations |

| `data_generator.py` | Default | Meaning |
|---|---|---|
| `--files` | 20 | Number of files (0 = run forever) |
| `--events-per-file` | 100 | Rows per file |
| `--interval` | 2.0 | Seconds between files |
| `--dirty-rate` | 0.0 | Share of rows to corrupt for testing, e.g. `0.05` |
| `--seed` | none | Fixed random seed for repeatable runs |

## Useful queries

```bash
# open the database shell (type \q to exit)
PGPASSWORD=spark_pass psql -h localhost -U spark_user -d ecommerce_stream
```
```sql
SELECT count(*) FROM user_events;
SELECT * FROM v_event_summary;
SELECT reject_reason, count(*) FROM rejected_events GROUP BY 1 ORDER BY 2 DESC;
SELECT * FROM pipeline_batch_metrics ORDER BY batch_id DESC LIMIT 10;
SELECT round(percentile_cont(0.5) WITHIN GROUP
       (ORDER BY EXTRACT(EPOCH FROM inserted_at - event_timestamp))::numeric, 2) AS median_latency_s
FROM user_events;
```

## Spark web UI
While Spark is running, open **http://localhost:4040** in your browser. The **Jobs** tab shows succeeded and failed work, and **Structured Streaming** shows input rate, processing rate and batch duration graphs.

## Performance test (optional)
```bash
python run_benchmark.py              # all scenarios, about 10 minutes
python run_benchmark.py --only S2    # one scenario
```
**Warning:** this empties the tables and the `data/` folder before each scenario. Results are saved to `logs/benchmark_results.json`.

## Start again from zero
```bash
PGPASSWORD=spark_pass psql -h localhost -U spark_user -d ecommerce_stream \
  -c "TRUNCATE user_events, rejected_events, pipeline_batch_metrics, user_events_staging"
rm -rf data logs
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `Command 'python' not found` | That terminal pane isn't using the environment. Run `source ~/venvs/ecom/bin/activate`. |
| `password authentication failed for user "spark_user"` | `sudo -u postgres psql -c "ALTER ROLE spark_user WITH PASSWORD 'spark_pass';"` |
| `Connection refused` | The database isn't running. Run `sudo service postgresql start`. |
| `can't open file '.../data_generator.py'` | You're in the wrong folder. `cd` to the main project folder and use `python ...`. |
| A `:` appears at the bottom of query output | That's a page viewer. Press `q`. |
| `JAVA_GATEWAY_EXITED` | Java isn't installed. Repeat Step 4 and check `java -version`. |
| `ClassNotFoundException: org.postgresql.Driver` | The JDBC driver is missing. Run `sudo apt install libpostgresql-jdbc-java`. |
| Files are in `data/input` but nothing happens | Spark has already processed those file names. Generate new files, or start again from zero. |
| Timestamps are off by your UTC offset | Keep the `-Duser.timezone=UTC` settings in the Spark job. |
