# TMDB Movie Data Analysis with PySpark

An end-to-end data pipeline that fetches movie data from the **TMDb (The Movie Database) API**, cleans and transforms it with **Apache Spark (PySpark)**, and produces KPIs, rankings, search queries and charts for the 19 movie IDs in the brief. 18 of them are valid films; ID `0` is invalid and is handled as a 404.

## Quick Links

| What | Where |
|------|-------|
| Main notebook | [`notebooks/tmdb_spark_analysis.ipynb`](./notebooks/tmdb_spark_analysis.ipynb) |
| Pipeline entry point | [`main.py`](./main.py) |
| Source code | [`src/`](./src/) |
| Tests | [`tests/`](./tests/) |
| Cleaned dataset | [`data/processed/`](./data/processed/) |
| Charts | [`figures/`](./figures/) |
| Key insights | [`reports/insights.md`](./reports/insights.md) |
| Final report | [`reports/final_report.md`](./reports/final_report.md) |

---

## Project Overview

The pipeline runs in seven stages, matching the sections printed by [`main.py`](./main.py):

| # | Stage | What happens | Code |
|---|-------|--------------|------|
| 1 | **Fetch** | Gets details and credits for each movie ID from the TMDb API (timeouts, retries, 404 handling, logging) and loads them into Spark | [`src/fetch_movies.py`](./src/fetch_movies.py) |
| 2 | **Clean & Save** | Applies all 11 cleaning steps from the brief with Spark column functions, then saves the result as Parquet and CSV | [`src/clean_movies.py`](./src/clean_movies.py), [`src/validate_clean_data.py`](./src/validate_clean_data.py) |
| 3 | **Explore** | Summary statistics, missing values, movies per year and correlations | [`src/explore_movies.py`](./src/explore_movies.py) |
| 4 | **KPIs** | All 10 rankings from one reusable `rank_movies()` function, with ROI from a Spark UDF | [`src/analyze_kpis.py`](./src/analyze_kpis.py) |
| 5 | **Searches** | The two search queries from the brief | [`src/search_bruce_willis.py`](./src/search_bruce_willis.py), [`src/search_uma_thurman.py`](./src/search_uma_thurman.py) |
| 6 | **Franchises & Directors** | Franchise vs standalone comparison, top franchises and top directors | [`src/compare_franchises.py`](./src/compare_franchises.py), [`src/analyze_franchises.py`](./src/analyze_franchises.py), [`src/analyze_directors.py`](./src/analyze_directors.py) |
| 7 | **Charts** | Five required charts plus a Top 10 revenue chart, saved to [`figures/`](./figures/) | [`src/visualize.py`](./src/visualize.py) |

---

## How Spark Is Used

| Task | Spark feature | Where in the code |
|------|---------------|-------------------|
| Running Spark | One `SparkSession` in local mode (`local[2]`, bound to `127.0.0.1`) for the whole project | [`src/spark_session.py`](./src/spark_session.py) → `get_spark()` |
| Loading the raw data | `spark.read.json` on the **JSON Lines** file (one movie per line, Spark's default JSON format). Nested fields like `genres` and `credits` stay as structs and arrays | [`src/fetch_movies.py`](./src/fetch_movies.py) → `fetch_movies()` |
| Flattening JSON columns | `F.transform` + `F.concat_ws` for genres, companies, countries, languages and cast; `F.filter` + `F.array_sort` for directors | [`src/clean_movies.py`](./src/clean_movies.py) → `join_names()`, `get_director()` |
| Type conversion | `try_cast` / `try_to_date`, so bad values become null instead of failing | [`src/clean_movies.py`](./src/clean_movies.py) → `clean_dataframe()` |
| `value_counts()` | `explode` + `groupBy().count()` | [`src/clean_movies.py`](./src/clean_movies.py) → `inspect_columns()` |
| Ranking | `Window` + `row_number()` | [`src/analyze_kpis.py`](./src/analyze_kpis.py) → `rank_movies()` |
| UDF | `roi_udf` (revenue / budget) registered with `@F.udf` | [`src/analyze_kpis.py`](./src/analyze_kpis.py) → `roi_udf()`, used in `all_kpis()` |
| Searches | `F.split` + `array_contains`, so only whole names match | [`src/search_bruce_willis.py`](./src/search_bruce_willis.py), [`src/search_uma_thurman.py`](./src/search_uma_thurman.py) |
| Aggregations | `groupBy().agg()` with `mean`, `median`, `sum`, `count`; `explode` for co-directors and genres | [`src/compare_franchises.py`](./src/compare_franchises.py), [`src/analyze_franchises.py`](./src/analyze_franchises.py), [`src/analyze_directors.py`](./src/analyze_directors.py), [`src/explore_movies.py`](./src/explore_movies.py) |
| Performance | `.cache()` on the analysis DataFrame; `spark.sql.shuffle.partitions = 4` for small data | [`main.py`](./main.py) → `main()`; [`src/spark_session.py`](./src/spark_session.py) |
| Storage | Parquet (keeps data types) + CSV (easy to open) | [`src/validate_clean_data.py`](./src/validate_clean_data.py) → `save_clean_data()`; [`src/save_results.py`](./src/save_results.py) → `save_csv()` |
| Charts | Spark groups the data; only the small result goes to pandas with `toPandas()` for Matplotlib | [`src/visualize.py`](./src/visualize.py) |

Spark does all the filtering and grouping. Only small, final results are converted to pandas.

---

## Data Flow

```text
TMDb API ──► raw JSONL file ──► clean (Spark) ──► cleaned DataFrame (cached) ──► KPIs, searches, charts
             (API called once)                          │
                                                        └──► saved as Parquet + CSV
```

- **The API is called only once.** The answers are saved to [`data/raw/tmdb_movies_raw.jsonl`](./data/raw/tmdb_movies_raw.jsonl), and later runs load this file instead.
- **The analysis runs on the cleaned DataFrame in memory**, not on the saved files. Cleaning 18 movies takes seconds, so it is redone on every run, which keeps the results in line with the current cleaning code.
- **Parquet** keeps the data types (dates, numbers), so it is the format to load in Spark:
  `spark.read.parquet("data/processed/tmdb_movies_clean.parquet")`
- **CSV** is for people: it opens in Excel or on GitHub without Spark.

---

## Project Structure

<pre>
tmdb-spark-analysis/
├── <a href="./data/">data/</a>
│   ├── <a href="./data/raw/">raw/</a>                        # Raw API answers (JSON Lines) and fetch_failures.json
│   └── <a href="./data/processed/">processed/</a>                  # Cleaned data (Parquet + CSV) and analysis results
├── <a href="./figures/">figures/</a>                        # Saved charts (PNG)
├── <a href="./notebooks/">notebooks/</a>
│   └── <a href="./notebooks/tmdb_spark_analysis.ipynb">tmdb_spark_analysis.ipynb</a>   # Main notebook (imports from src/)
├── <a href="./reports/">reports/</a>
│   ├── <a href="./reports/insights.md">insights.md</a>                 # Plain-English summary of findings
│   └── <a href="./reports/final_report.md">final_report.md</a>             # Methodology and detailed results
├── <a href="./src/">src/</a>
│   ├── <a href="./src/__init__.py">__init__.py</a>
│   ├── <a href="./src/spark_session.py">spark_session.py</a>            # Creates the SparkSession
│   ├── <a href="./src/fetch_movies.py">fetch_movies.py</a>             # API extraction, retries, logging, caching
│   ├── <a href="./src/clean_movies.py">clean_movies.py</a>             # Cleaning and transformation
│   ├── <a href="./src/validate_clean_data.py">validate_clean_data.py</a>      # Saves and checks the cleaned data
│   ├── <a href="./src/save_results.py">save_results.py</a>             # Saves small results as CSV
│   ├── <a href="./src/explore_movies.py">explore_movies.py</a>           # Basic EDA
│   ├── <a href="./src/analyze_kpis.py">analyze_kpis.py</a>             # roi_udf, rank_movies() and all 10 KPIs
│   ├── <a href="./src/search_bruce_willis.py">search_bruce_willis.py</a>      # Search query 1
│   ├── <a href="./src/search_uma_thurman.py">search_uma_thurman.py</a>       # Search query 2
│   ├── <a href="./src/compare_franchises.py">compare_franchises.py</a>       # Franchise vs standalone comparison
│   ├── <a href="./src/analyze_franchises.py">analyze_franchises.py</a>       # Top franchises
│   ├── <a href="./src/analyze_directors.py">analyze_directors.py</a>        # Top directors
│   └── <a href="./src/visualize.py">visualize.py</a>                # Chart generation
├── <a href="./tests/">tests/</a>
│   ├── <a href="./tests/conftest.py">conftest.py</a>                 # Shared Spark session for tests
│   └── <a href="./tests/test_pipeline.py">test_pipeline.py</a>            # API, cleaning, UDF, KPI and search tests
├── <a href="./main.py">main.py</a>                         # Runs the full pipeline
├── <a href="./requirements.txt">requirements.txt</a>                # Python packages
├── .env                            # API key (not committed)
├── <a href="./.gitignore">.gitignore</a>
└── <a href="./README.md">README.md</a>
</pre>

---

## Setup

### 1. Requirements

- **Python 3.10 – 3.12** (newer versions may not be supported by PySpark yet)
- **Java 17** (Spark runs on Java), with `JAVA_HOME` set and Java's `bin` folder in `Path`
- **Windows only:** `winutils.exe` and `hadoop.dll` in `C:\hadoop\bin`, `HADOOP_HOME=C:\hadoop`, and the Microsoft Visual C++ Redistributable

Install on Windows:

```powershell
winget install EclipseAdoptium.Temurin.17.JDK
winget install Python.Python.3.12
winget install Microsoft.VCRedist.2015+.x64
winget install Microsoft.VCRedist.2010.x64
```

Then set `JAVA_HOME` and add Java to `Path`. Replace the folder name with yours, which you can find with `dir "C:\Program Files\Eclipse Adoptium"`:

```powershell
$jdk = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
[Environment]::SetEnvironmentVariable("JAVA_HOME", $jdk, "User")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$userPath;$jdk\bin", "User")
```

Close **all** VS Code windows, reopen the project and check with `java -version`.

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

A free key is available at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api). The `.env` file is listed in [`.gitignore`](./.gitignore) and is never committed.

### 4. Run the pipeline

**Option A – Terminal**

```bash
python main.py
```

**Option B – Notebook (VS Code or Jupyter)**

Open [`notebooks/tmdb_spark_analysis.ipynb`](./notebooks/tmdb_spark_analysis.ipynb), choose the `venv` kernel and run all cells.

While Spark is running, the Spark UI is available at <http://localhost:4040>.

The raw API answers are saved in [`data/raw/`](./data/raw/), so the pipeline can be re-run offline. To fetch fresh data, delete `data/raw/tmdb_movies_raw.jsonl`.

### 5. Run the tests

```bash
python -m pytest
```

The tests in [`tests/test_pipeline.py`](./tests/test_pipeline.py) use fake API answers, so they need no API key or internet. On Windows they take about 1–2 minutes, mostly for starting Spark. They check that:

- a 404 (like ID `0`) is skipped without retrying
- a timeout is retried, and the fetch gives up after 3 attempts
- the cleaning follows the brief (column order, duplicates, unreleased movies, zeros, 0 votes, placeholders)
- the ROI UDF and all 10 KPIs work
- the search only matches whole actor names

### 6. Troubleshooting (Windows)

| Problem | Fix |
|---------|-----|
| `Java not found and JAVA_HOME environment variable is not set`, or `java` is not recognized | Set `JAVA_HOME` and `Path` as in step 1, then close **all** VS Code windows and reopen. Terminals that are already open keep the old settings. |
| `Python worker exited unexpectedly` / `Can not open socket ... timed out` when using the UDF | Already handled in [`src/spark_session.py`](./src/spark_session.py) (`local[2]`, `127.0.0.1`). Also add the project folder to Windows Defender exclusions, which also makes runs faster. |
| Errors after moving the project folder | The `venv` remembers its original location. Delete it and create it again (step 2). |

---

## API Robustness

All in [`src/fetch_movies.py`](./src/fetch_movies.py):

- **10-second timeout** on every request.
- **Up to 3 attempts** per movie if the request times out, the connection fails or the server returns an error (waits 2 s, then 4 s).
- **404 handling:** invalid IDs (e.g. `0`) are logged, skipped without retrying and recorded in [`data/raw/fetch_failures.json`](./data/raw/fetch_failures.json).
- **Logging** with Python's `logging` module instead of `print`.

---

## Outputs

| Output | Location |
|--------|----------|
| Raw API answers | [`data/raw/tmdb_movies_raw.jsonl`](./data/raw/tmdb_movies_raw.jsonl) (read by Spark) and [`data/raw/tmdb_movies_raw.json`](./data/raw/tmdb_movies_raw.json) (readable copy) |
| Failed / invalid IDs | [`data/raw/fetch_failures.json`](./data/raw/fetch_failures.json) |
| Cleaned dataset (22 columns, in the order from the brief) | [`data/processed/tmdb_movies_clean.parquet`](./data/processed/tmdb_movies_clean.parquet) and [`data/processed/tmdb_movies_clean.csv`](./data/processed/tmdb_movies_clean.csv) |
| Franchise vs standalone | [`data/processed/franchise_vs_standalone.csv`](./data/processed/franchise_vs_standalone.csv) |
| Franchise analysis | [`data/processed/franchise_performance.csv`](./data/processed/franchise_performance.csv) |
| Director analysis | [`data/processed/director_performance.csv`](./data/processed/director_performance.csv) |
| Search results | [`data/processed/bruce_willis_search.csv`](./data/processed/bruce_willis_search.csv), [`data/processed/uma_thurman_search.csv`](./data/processed/uma_thurman_search.csv) |

The Parquet output is a folder: the `part-*.snappy.parquet` file holds the data, and the empty `_SUCCESS` file means the write finished without errors.

### Figures

| Chart | File |
|-------|------|
| Revenue vs Budget | [`figures/revenue_vs_budget.png`](./figures/revenue_vs_budget.png) |
| Average ROI by Genre | [`figures/roi_by_genre.png`](./figures/roi_by_genre.png) |
| Popularity vs Rating | [`figures/popularity_vs_rating.png`](./figures/popularity_vs_rating.png) |
| Yearly Box Office Revenue | [`figures/yearly_box_office.png`](./figures/yearly_box_office.png) |
| Franchise vs Standalone | [`figures/franchise_vs_standalone.png`](./figures/franchise_vs_standalone.png) |
| Top 10 Movies by Revenue | [`figures/top_10_revenue.png`](./figures/top_10_revenue.png) |

---

## Notes

**Dataset size.** ID `0` is not a valid TMDb movie and returns a 404, so the analysis runs on the remaining **18 movies**.

**Empty search results.** Both searches work as specified and check the full cast and every director. Neither Bruce Willis nor Uma Thurman appears in any of the 18 films, and none is directed by Quentin Tarantino, so both return 0 rows. The notebook shows this check.

**No index in Spark.** Spark DataFrames have no row index, so step 11 ("reset index") is handled by sorting by `id` for a fixed, repeatable order.

**Co-directors.** A movie with two directors (e.g. Anthony and Joe Russo) counts for each director in the director analysis.

**Units.** Budget, revenue and profit are in **millions of USD**. ROI is `revenue / budget`, and the ROI rankings only include movies with a budget of at least $10M.

**Scaling up.** The brief covers 19 IDs. For TMDb's full catalogue (about 1 million movies), the ID list would come from TMDb's daily ID export, the fetch would run in parallel with checkpoints, and the analysis would load the saved Parquet instead of re-cleaning every run.

---

## Author

**Umutoni Justine**