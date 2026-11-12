# How to run the pipeline (Windows)

The running process from start to finish. Run every command in the **VS Code terminal (PowerShell)**
from the project folder:

```powershell
cd C:\Users\User\Desktop\flight-price-pipeline
```

---

## Run everything with one command

From the project folder, in the VS Code terminal:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all.ps1
```

[`scripts/run_all.ps1`](../scripts/run_all.ps1) does the whole process in order, checking each step
and stopping with a clear message at the first problem:

| Step | What it does |
|---|---|
| 1 | Checks that Docker is running, that `.env` exists, and that the dataset is in `data\` |
| 2 | `docker compose up -d`, then waits until all services are **healthy** |
| 3 | Checks that the DAG loaded with no import errors (and that it's switched on) |
| 4 | Checks the Gmail connection (login only, no email sent) |
| 5 | Triggers the DAG with its own run ID, for example `manual__run_all_2026-11-11T14-05-00`, and waits for **success** |
| 6 | Shows the results from PostgreSQL: the run log, top airlines by fare, peak vs non-peak, top routes |
| 7 | Opens the KPI report [`data/reports/kpi_report.html`](../data/reports/kpi_report.html) in your browser |

Options:

| Option | Effect |
|---|---|
| `-Download` | If the dataset is missing, download it from Kaggle first (needs `kaggle.json`, see [`KAGGLE_SETUP.md`](KAGGLE_SETUP.md)) |
| `-SendTestEmail` | Also send a test email in step 4 |
| `-SkipEmailCheck` | Skip step 4 |
| `-NoOpen` | Don't open the report at the end |
| `-Force` | Load the file even if it's the same as last time (ignores the watermark) |
| `-TimeoutMinutes 20` | Wait longer for the run (default 15) |

The run ID printed by the script is the same one shown in the Airflow UI, in the SUCCESS email, in
`analytics.pipeline_run_log` and at the top of the KPI report. That is your proof that the results
come from this run.

The step-by-step version of the same process is below.

---

## 0. One-time setup (already done on this computer)

| Item | Check |
|---|---|
| Docker Desktop installed and **running** (whale icon in the taskbar) | `docker --version` |
| `.env` file exists with passwords and email settings | `Get-Content .env` |
| Gmail App Password in `.env` (`SMTP_PASSWORD`, no spaces) | see [`EMAIL_SETUP.md`](EMAIL_SETUP.md) |
| CSV in the data folder | `dir data` shows `Flight_Price_Dataset_of_Bangladesh.csv`. To get it: [`KAGGLE_SETUP.md`](KAGGLE_SETUP.md) |
| `logs` folder exists | `mkdir logs -Force` |

---

## 1. Start the stack

```powershell
docker compose up -d
```

The first time, this downloads the images (MySQL, PostgreSQL, Airflow), which takes a few minutes.
After that, it starts in about 30 seconds.

## 2. Check that everything is up

```powershell
docker compose ps
```

| Service | Expected status |
|---|---|
| `airflow-db` | running (healthy) |
| `mysql-staging` | running (healthy) |
| `postgres-analytics` | running (healthy) |
| `airflow-init` | exited (0). It only prepares Airflow, then stops. |
| `airflow-apiserver` | running (healthy after about 1 minute). This is the web UI. |
| `airflow-dag-processor` | running. It reads the DAG files. |
| `airflow-scheduler` | running (healthy) |

## 3. (Optional) Check email

```powershell
docker compose exec -w /opt/airflow/dags airflow-scheduler python -m flight_pipeline.check_email --send
```

All lines should say `[OK]`, and a test email should arrive.

## 4. Open Airflow

Go to **[http://localhost:8080](http://localhost:8080)** and log in with `admin` / `admin`.

`flight_price_pipeline` should be in the list, switched **on** (blue toggle). If you see a red
"Broken DAG" banner, see Troubleshooting below.

## 5. Run the pipeline

The pipeline runs **automatically every day at 00:00 UTC**. To run it now:

* **UI:** open **Dags** (left menu) → `flight_price_pipeline` → **Trigger** (top right). The trigger form also lets you change the params.
* **Terminal:**
  ```powershell
  docker compose exec airflow-scheduler airflow dags trigger flight_price_pipeline
  ```

## 6. Watch it run

Click the DAG → **Grid** view. The tasks run in this order (about 30–60 seconds in total):

```
extract   : check_source_file → check_watermark → create_staging_tables → extract_csv_to_mysql
transform : validate_data → transform_data → kpis (4 in parallel)
load      : create_analytics_tables → load_to_postgres → verify_postgres_load → update_watermark → build_kpi_report → notify_success
```

| Colour | Meaning |
|---|---|
| light green | running |
| dark green | success |
| yellow / orange | up for retry (Airflow will retry by itself) |
| red | failed (you also get a FAILED email) |
| pink / grey | skipped or not run because an earlier task failed |

To see what a task did, click it → **Logs**.

## 7. Check the results

**KPI charts:** open [`data/reports/kpi_report.html`](../data/reports/kpi_report.html) in your browser
(double-click it in File Explorer, or right-click it in VS Code → **Reveal in File Explorer**). The
pipeline rebuilds it at the end of every successful run. It shows the headline numbers plus
charts for all 4 KPIs: average fare by airline, seasonal variation, bookings by airline and top
routes. Hover a bar for details, use **Light / dark** to switch the colours, and **Show the numbers as
tables** for exact values. It works offline, so it's ready for a presentation.

**Email:** you should receive `[Airflow] SUCCESS: flight_price_pipeline loaded … rows`.

**Database:** open the analytics database:

```powershell
docker compose exec postgres-analytics psql -U analytics_user -d flight_analytics
```

```sql
SELECT * FROM analytics.pipeline_run_log ORDER BY loaded_at DESC LIMIT 3;   -- rows in / valid / rejected / loaded
SELECT airline, avg_total_fare, fare_rank FROM analytics.kpi_avg_fare_by_airline ORDER BY fare_rank;
SELECT * FROM analytics.v_peak_vs_offpeak;                                   -- seasonal fare variation
SELECT airline, booking_count, booking_share_pct FROM analytics.kpi_booking_count_by_airline ORDER BY booking_rank;
SELECT * FROM analytics.v_top_routes;                                        -- most popular routes
\q
```

**Data quality findings** are in the MySQL staging database:

```powershell
docker compose exec mysql-staging mysql -u staging_user -pstaging_pass flight_staging -e "SELECT rule_name, severity, COUNT(*) AS n FROM dq_issues GROUP BY 1,2 ORDER BY n DESC;"
```

## 8. Stop the stack

```powershell
docker compose stop        # stop, keep all data (start again with: docker compose start)
docker compose down        # remove containers, KEEP data (volumes)
docker compose down -v     # remove containers AND all data (full reset)
```

---

## Watermark: why a run can be skipped

If the CSV in `data\` is exactly the same file as the last successful load, the
`extract.check_watermark` task stops the run: everything after it shows as **skipped** (pink) and the
run is still **green**. Nothing is reloaded, because nothing changed. `run_all.ps1` prints
*"skipped by the watermark (same file)"*.

To load it anyway (for example after changing the code, or for a demo):

* **Script:** `powershell -ExecutionPolicy Bypass -File scripts\run_all.ps1 -Force`
* **UI:** Trigger, then switch on `force_full_reload` in the form
* **Command line:** `docker compose exec airflow-scheduler airflow dags trigger flight_price_pipeline --conf '{\"force_full_reload\": true}'`

Replacing the CSV with a new file is detected automatically: its checksum is different.

---

## The Airflow 3 interface

The project runs on **Airflow 3.1.3**: a dark or light interface with the menu on the left.
Log in at [http://localhost:8080](http://localhost:8080) with `admin` / `admin`.

| To | Click |
|---|---|
| See the pipeline | **Dags** (left menu) → `flight_price_pipeline` |
| Run it now | **Trigger** (top right of the DAG page); the params can be edited in the form |
| Watch the tasks | **Grid** (squares per run) or **Graph** (the extract → transform → load flow) |
| Read a task's log | click a task square → **Logs** |
| See the DAG description and rules | the DAG page's **Details / Docs** |
| Dark or light mode | **User** menu (bottom left) → switch the colour mode. By default it follows your computer's setting. |

The Airflow services are `airflow-apiserver` (the web interface and API), `airflow-scheduler` (runs the
tasks) and `airflow-dag-processor` (reads the DAG files).

---

## After changing something

| You changed | Do this |
|---|---|
| `.env` (passwords, email, thresholds, retries) | `docker compose up -d` |
| Python code in [`dags\`](../dags/) | Nothing. Airflow picks it up within about 30 seconds. |
| [`docker-compose.yml`](../docker-compose.yml) | `docker compose up -d` |
| The CSV in [`data\`](../data/) | Trigger the DAG again. Re-runs replace the data, with no duplicates. |

## Troubleshooting

| Problem | Fix |
|---|---|
| `WARN ... variable is not set` / `.env not found` | `.env` is missing. Create it from [`.env.example`](../.env.example) (see `EMAIL_SETUP.md`, Step 3). |
| `error during connect` / `docker` not found | Start **Docker Desktop** and wait until it says *running*. |
| Old containers from an earlier setup are still listed | Run `docker compose up -d --remove-orphans` |
| Port 8080 already in use | Another Airflow, such as the course demo, is running. Stop it: `docker compose down` in that folder. |
| Red "Broken DAG" banner in the UI | Click it to read the error. Usually a typo in [`dags\`](../dags/). |
| `check_source_file` keeps retrying | The CSV isn't in [`data\`](../data/), or the file name is different. |
| `validate_data` failed | The data quality is too low. See `dq_issues` (step 7) and [`RUNBOOK.md`](RUNBOOK.md). |
| Any other red task | Click it → **Logs**, then follow [`RUNBOOK.md`](RUNBOOK.md), section 4. |
| See container logs | `docker compose logs airflow-scheduler --tail 50` |
