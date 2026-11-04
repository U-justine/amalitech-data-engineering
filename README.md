# TMDB Movie Data Analysis with PySpark

An end-to-end data pipeline that fetches movie data from the **TMDb (The Movie Database) API**, cleans and transforms it with **Apache Spark (PySpark)**, and produces KPIs, rankings, search queries and visualizations for the 19 movie IDs in the brief (18 valid films; ID `0` is invalid and is handled as a 404).

## Quick Links

| What | Where |
|------|-------|
| Main notebook | [`notebooks/tmdb_spark_analysis.ipynb`](./notebooks/tmdb_spark_analysis.ipynb) |
| Pipeline entry point | [`main.py`](./main.py) |
| Source modules | [`src/`](./src/) |
| Cleaned dataset | [`data/processed/`](./data/processed/) |
| Charts | [`figures/`](./figures/) |
| Insights summary | [`reports/insights.md`](./reports/insights.md) |
| Final report | [`reports/final_report.md`](./reports/final_report.md) |

---

## Project Overview

The pipeline runs in seven stages, matching the sections printed by `main.py`:

1. **Fetch** – Pulls details and credits for each movie ID from the TMDb API (timeouts, retries, 404 handling, logging) and loads them into a Spark DataFrame with `spark.read.json`.
2. **Clean & Save** – Follows all 11 cleaning steps in the brief using Spark's built-in column functions (no row-by-row Python loops), then saves the result as Parquet and CSV.
3. **Explore** – Summary statistics, missing values, movies per year and correlations.
4. **KPIs** – All 10 rankings through one reusable `rank_movies()` function built on a Spark window function, with ROI from a Spark UDF.
5. **Searches** – The two required search queries.
6. **Franchises & Directors** – Franchise vs standalone comparison, top franchises and top directors.
7. **Charts** – Five required charts plus a Top 10 revenue chart, saved to `figures/`.

## How Spark is used

| Task | Spark feature |
|------|---------------|
| Running Spark | `SparkSession` in local mode (`local[2]`, bound to `127.0.0.1`), one session for the whole project |
| Loading nested JSON | `spark.read.json` keeps `genres`, `credits` etc. as structs and arrays |
| Flattening JSON columns | `F.transform`, `F.filter`, `F.concat_ws`, `F.array_sort` |
| Type conversion | `try_cast` / `try_to_date` (bad values become null instead of failing) |
| `value_counts()` | `explode` + `groupBy().count()` |
| Ranking | `Window` + `row_number()` |
| UDF | `roi_udf` (revenue / budget) registered with `@F.udf` |
| Aggregations | `groupBy().agg()` with `mean`, `median`, `sum`, `count` |
| Performance | `.cache()` on the analysis DataFrame, `spark.sql.shuffle.partitions = 4` for small data |
| Storage | Parquet (keeps data types) + one CSV for easy reading |

Spark does all the grouping and filtering. Only small, final results are converted with `toPandas()` for Matplotlib.

## Data Flow

```text
TMDb API ──► data/raw/tmdb_movies_raw.jsonl ──► clean (Spark) ──► cleaned DataFrame (cached) ──► KPIs, searches, charts
               (API called only once)                                    │
                                                                         └──► saved as Parquet + CSV
```

- **The API is called only once.** Later runs load the saved raw JSONL file instead.
- **The analysis runs on the cleaned DataFrame in memory.** Cleaning 18 movies takes seconds, so it is redone on every run. This keeps the results in line with the current cleaning code.
- **Parquet** keeps the data types (dates, numbers) and is the format to load in Spark:
  `spark.read.parquet("data/processed/tmdb_movies_clean.parquet")`.
  **CSV** is for people: it opens in Excel or on GitHub without Spark.

---

## Project Structure

```text
tmdb-spark-analysis/
├── data/
│   ├── raw/                        # Raw API answers (JSON Lines) and fetch_failures.json
│   └── processed/                  # Cleaned data (Parquet + CSV) and analysis results
├── figures/                        # Saved charts (PNG)
├── notebooks/
│   └── tmdb_spark_analysis.ipynb   # Main notebook (imports from src/)
├── reports/
│   ├── insights.md                 # Plain-English summary of findings
│   └── final_report.md             # Methodology and detailed results
├── src/
│   ├── __init__.py
│   ├── spark_session.py            # Creates the SparkSession
│   ├── fetch_movies.py             # API extraction, retries, logging, caching
│   ├── clean_movies.py             # Cleaning and transformation
│   ├── validate_clean_data.py      # Saves and checks the cleaned data
│   ├── save_results.py             # Saves small results as CSV
│   ├── explore_movies.py           # Basic EDA
│   ├── analyze_kpis.py             # roi_udf, rank_movies() and all 10 KPIs
│   ├── search_bruce_willis.py      # Search query 1
│   ├── search_uma_thurman.py       # Search query 2
│   ├── compare_franchises.py       # Franchise vs standalone comparison
│   ├── analyze_franchises.py       # Top franchises
│   ├── analyze_directors.py        # Top directors
│   └── visualize.py                # Chart generation
├── tests/
│   ├── conftest.py                 # Shared Spark session for tests
│   └── test_pipeline.py            # API, cleaning, UDF, KPI and search tests
├── main.py                         # Runs the full pipeline
├── requirements.txt
├── .env                            # API key (not committed)
├── .gitignore
└── README.md
```

---

## Setup

### 1. Requirements

- **Python 3.10 – 3.12** (newer versions may not be supported by PySpark yet)
- **Java 17** (Spark runs on Java), with `JAVA_HOME` set and Java's `bin` folder in `Path`
- **Windows only:** `winutils.exe` and `hadoop.dll` in `C:\hadoop\bin`, `HADOOP_HOME=C:\hadoop`, and the Microsoft Visual C++ Redistributable

Windows commands used for this project:

```powershell
winget install EclipseAdoptium.Temurin.17.JDK
winget install Python.Python.3.12
winget install Microsoft.VCRedist.2015+.x64
winget install Microsoft.VCRedist.2010.x64
```

Then set `JAVA_HOME` and add Java to `Path` (replace the folder name with yours from `dir "C:\Program Files\Eclipse Adoptium"`):

```powershell
$jdk = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
[Environment]::SetEnvironmentVariable("JAVA_HOME", $jdk, "User")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$userPath;$jdk\bin", "User")
```

Close and reopen VS Code (all windows), then check with `java -version`.

### 2. Virtual environment and packages

```bash
py -3.12 -m venv venv          # macOS / Linux: python3 -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. TMDb API key

Create a `.env` file in the project folder:

```env
TMDB_API_KEY=your_api_key_here
```

A free key is available at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api). The `.env` file is listed in `.gitignore` and is never committed.

### 4. Run the pipeline

**Option A – Terminal**

```bash
python main.py
```

**Option B – Notebook (VS Code or Jupyter)**

Open `notebooks/tmdb_spark_analysis.ipynb`, choose the `venv` kernel and run all cells.

While Spark is running, the Spark UI is available at <http://localhost:4040>.

Raw API answers are cached in `data/raw/`, so the pipeline can be re-run offline. Delete `data/raw/tmdb_movies_raw.jsonl` to fetch fresh data.

### 5. Run the tests

```bash
python -m pytest
```

The tests use fake API answers, so they need no API key or internet. On Windows they take about 1–2 minutes, mostly for starting Spark. They check that:

- a 404 (like ID `0`) is skipped without retrying
- a timeout is retried, and the fetch gives up after 3 attempts
- the cleaning follows the brief (column order, duplicates, unreleased movies, zeros, 0 votes, placeholders)
- the ROI UDF and all 10 KPIs work
- the search only matches whole actor names

### 6. Troubleshooting (Windows)

| Problem | Fix |
|---------|-----|
| `Java not found and JAVA_HOME environment variable is not set`, or `java` is not recognized | Set `JAVA_HOME` and `Path` as shown in step 1, then **close all VS Code windows** and reopen. Open terminals keep the old settings. |
| `Python worker exited unexpectedly` / `Can not open socket ... timed out` when using the UDF | Already handled in `spark_session.py` (`local[2]`, `127.0.0.1`). Also add the project folder to Windows Defender exclusions; this also makes runs faster. |
| Errors after moving the project folder | The `venv` remembers its original location, so delete it and create it again (step 2). |

---

## API Robustness

- **10-second timeout** on every request.
- **Up to 3 attempts** per movie if the request times out, the connection fails or the server returns an error (waits 2 s, then 4 s).
- **404 handling** – invalid IDs (e.g. `0`) are logged, skipped without retrying, and recorded in `data/raw/fetch_failures.json`.
- **Logging** with Python's `logging` module instead of `print`.

---

## Outputs

| Output | Location |
|--------|----------|
| Raw API answers | `data/raw/tmdb_movies_raw.jsonl` (read by Spark) and `tmdb_movies_raw.json` (readable copy) |
| Failed / invalid IDs | `data/raw/fetch_failures.json` |
| Cleaned dataset (22 columns, in the order from the brief) | `data/processed/tmdb_movies_clean.parquet` and `.csv` |
| Franchise vs standalone | `data/processed/franchise_vs_standalone.csv` |
| Franchise analysis | `data/processed/franchise_performance.csv` |
| Director analysis | `data/processed/director_performance.csv` |
| Search results | `data/processed/bruce_willis_search.csv`, `uma_thurman_search.csv` |

The Parquet output is a folder: `part-*.snappy.parquet` holds the data and the empty `_SUCCESS` file marks a completed write.

### Figures

| Chart | File |
|-------|------|
| Revenue vs Budget | `figures/revenue_vs_budget.png` |
| Average ROI by Genre | `figures/roi_by_genre.png` |
| Popularity vs Rating | `figures/popularity_vs_rating.png` |
| Yearly Box Office Revenue | `figures/yearly_box_office.png` |
| Franchise vs Standalone | `figures/franchise_vs_standalone.png` |
| Top 10 Movies by Revenue | `figures/top_10_revenue.png` |

---

## Notes

**Dataset size.** ID `0` is not a valid TMDb movie and returns a 404, so the analysis runs on the remaining **18 movies**.

**Empty search results.** Both searches are implemented as specified and check the full cast and every director. Neither Bruce Willis nor Uma Thurman appears in any of the 18 films, and none is directed by Quentin Tarantino, so both return 0 rows. The notebook shows this check.

**No index in Spark.** Spark DataFrames have no row index, so step 11 ("reset index") is handled by sorting by `id` for a fixed, repeatable order.

**Co-directors.** A movie with two directors (e.g. Anthony and Joe Russo) counts for each director in the director analysis.

**Units.** Budget, revenue and profit are in **millions of USD**. ROI is `revenue / budget`; ROI rankings only include movies with a budget of at least $10M.

**Scaling up.** The brief covers 19 IDs. For TMDb's full catalogue (about 1 million movies), the ID list would come from TMDb's daily ID export, the fetch would run in parallel with checkpoints, and the analysis would load the saved Parquet instead of re-cleaning every run.

---

## Author

**Umutoni Justine**