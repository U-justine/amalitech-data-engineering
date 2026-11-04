# TMDB Movie Data Analysis with PySpark – Final Report


## 1. Objective

Build a movie data pipeline with Apache Spark that fetches data from the TMDb API, cleans and transforms it, calculates KPIs, analyzes franchises and directors, and presents the findings with Matplotlib.

## 2. Tools

| Tool | Use |
|------|-----|
| PySpark 4 (local mode) | Cleaning, transformation, KPIs and aggregations |
| requests | TMDb API calls |
| Matplotlib, adjustText | Charts |
| pytest | Tests |
| Git / GitHub | Version control |

Spark runs in local mode (`local[2]`, bound to `127.0.0.1`) through one shared `SparkSession` (`src/spark_session.py` → `get_spark()`). Two cores are enough for this small dataset and avoid Python worker timeouts on Windows.

The whole pipeline is run by `main.py`, or step by step in `notebooks/tmdb_spark_analysis.ipynb`.

## 3. Methodology

### 3.1 Data extraction

*Code: `src/fetch_movies.py` → `fetch_movie()`, `download_movies()`, `fetch_movies()`*

- 19 movie IDs were requested from `/movie/{id}` with `append_to_response=credits`, so cast and crew come in the same call.
- Each request has a 10-second timeout and up to 3 attempts, waiting longer between attempts (2 s, then 4 s).
- ID `0` returned **404 Not Found**. It was logged, skipped without retrying and saved to `data/raw/fetch_failures.json`, leaving **18 movies**.
- The answers were saved as **JSON Lines** (`data/raw/tmdb_movies_raw.jsonl`, one movie per line) and loaded with `spark.read.json`, which reads JSON Lines by default and keeps the nested data as Spark structs and arrays.
- The raw file acts as a cache: later runs load it instead of calling the API again.

### 3.2 Cleaning and transformation

*Code: `src/clean_movies.py` → `clean_dataframe()`, with helpers `join_names()`, `get_director()` and `inspect_columns()`*

| Step | Spark implementation |
|------|----------------------|
| 1. Drop irrelevant columns | `df.drop(...)` |
| 2–3. Flatten JSON columns | `belongs_to_collection.name`; `F.transform` + `F.concat_ws("\|")` for genres, companies, countries, languages (`join_names()`) |
| Cast, director, sizes | Names joined from `credits.cast`; directors found with `F.filter(job == "Director")` + `F.array_sort` (`get_director()`); `F.size` for cast and crew size |
| 4. Inspect columns | `explode(split(...))` + `groupBy().count()`, the Spark version of `value_counts()` (`inspect_columns()`) |
| 5. Data types | `try_cast` to double/long, `try_to_date` for `release_date` |
| 6. Unrealistic values | 0 budget/revenue/runtime → null; budget and revenue → million USD; `vote_average` → null when `vote_count = 0`; "No Data" / empty text → null |
| 7. Duplicates and missing keys | `dropDuplicates(["id"])`, `dropna(subset=["id", "title"])` |
| 8. At least 10 values | `dropna(thresh=10)` |
| 9. Released only | `filter(status == "Released")`, then drop `status` |
| 10. Column order | `select(FINAL_COLS)` |
| 11. Reset index | Spark has no index; rows are sorted by `id` for a fixed order |

The cleaned data has **18 rows and 22 columns**, with no duplicate IDs and no missing titles. It is saved and checked by `src/validate_clean_data.py` → `save_clean_data()`:

- **Parquet** (`data/processed/tmdb_movies_clean.parquet`) keeps the data types and is read back to check the row count, column order, duplicate IDs and missing titles.
- **CSV** (`data/processed/tmdb_movies_clean.csv`) is a copy that opens in Excel or on GitHub.

For the analysis, `add_metrics()` (`src/clean_movies.py`) adds four columns: `profit_musd`, `roi`, `is_franchise` and `release_year`. This DataFrame is cached in `main.py` because every later step reuses it.

**Data flow.** The analysis runs on the cleaned DataFrame in memory, not on the saved files. The API is called only once (the raw JSONL file is reused), and cleaning 18 movies takes seconds. Cleaning is therefore redone on every run, which keeps the results in line with the current cleaning code. With much larger data, the analysis would load the Parquet file instead.

```text
TMDb API ──► raw JSONL ──► clean (Spark) ──► cleaned DataFrame (cached) ──► KPIs, searches, charts
                                                    └──► Parquet + CSV
```

### 3.3 KPIs

*Code: `src/analyze_kpis.py` → `roi_udf()`, `rank_movies()`, `all_kpis()`, `show_all_kpis()`*

`rank_movies()` filters by minimum votes or budget when needed, then ranks with `row_number()` over a window ordered by the chosen column (title breaks ties). For the KPI rankings, ROI is calculated with a Spark UDF, `roi_udf`. All 10 KPIs are built in `all_kpis()` from this one function.

### 3.4 Searches, franchises and directors

*Code: `src/search_bruce_willis.py` → `find_bruce_willis()`, `src/search_uma_thurman.py` → `find_uma_thurman()`, `src/compare_franchises.py` → `compare_franchise_vs_standalone()`, `src/analyze_franchises.py` → `analyze_franchise_performance()`, `src/analyze_directors.py` → `analyze_director_performance()`*

- Genres, cast and directors are split into arrays and matched with `array_contains`, so only whole names match.
- Franchise vs standalone, top franchises and top directors use `groupBy().agg()`. Median ROI uses `F.median`.
- A movie with two directors counts for each director (`explode` on the director list).
- Results are saved as CSV in `data/processed/` through `src/save_results.py` → `save_csv()`.

### 3.5 Visualization

*Code: `src/visualize.py`*

Spark does the grouping. Only the small results are converted with `toPandas()` and plotted with Matplotlib. Each chart is saved to `figures/` by `save_plot()`, and is also shown when running in the notebook.

### 3.6 Testing

*Code: `tests/test_pipeline.py`, `tests/conftest.py`*

8 pytest tests use fake API answers, so they need no API key or internet. They cover 404 handling, retries and timeouts, the cleaning rules, the ROI UDF, all 10 KPIs and whole-name search matching. All 8 pass.

## 4. Results

### 4.1 Top movies

| KPI | #1 | Value |
|-----|----|-------|
| Highest revenue | Avengers: Endgame | $2,938.57M |
| Highest budget | Avengers: Endgame | $356.00M |
| Highest profit | Avatar | $2,686.71M |
| Lowest profit | Star Wars: The Last Jedi | $1,034.41M |
| Highest ROI (budget ≥ $10M) | Avatar | 12.34x |
| Lowest ROI (budget ≥ $10M) | Star Wars: The Last Jedi | 4.45x |
| Most voted | The Avengers | 40,161 votes |
| Highest rated (≥ 10 votes) | Avengers: Endgame | 8.25 |
| Lowest rated (≥ 10 votes) | Jurassic World: Fallen Kingdom | 6.52 |
| Most popular | Avengers: Endgame | 88.15 |

### 4.2 Searches

Both searches returned **0 movies**. No movie in the dataset stars Bruce Willis or Uma Thurman, or is directed by Quentin Tarantino.

### 4.3 Franchise vs standalone

| Type | Movies | Mean revenue | Median ROI | Mean budget | Mean popularity | Mean rating |
|------|--------|--------------|------------|-------------|-----------------|-------------|
| Franchise | 16 | 1,691.47 | 7.84 | 218.00 | 37.73 | 7.39 |
| Standalone | 2 | 1,765.14 | 9.62 | 180.00 | 40.67 | 7.44 |

### 4.4 Top franchises (by total revenue)

| Franchise | Movies | Total budget | Total revenue | Mean revenue | Mean rating |
|-----------|--------|--------------|---------------|--------------|-------------|
| The Avengers Collection | 4 | 1,111.0 | 7,915.20 | 1,978.80 | 7.96 |
| Star Wars Collection | 2 | 545.0 | 3,402.63 | 1,701.32 | 6.98 |
| Jurassic Park Collection | 2 | 320.0 | 2,982.01 | 1,491.00 | 6.61 |
| Avatar Collection | 1 | 237.0 | 2,923.71 | 2,923.71 | 7.61 |
| Frozen Collection | 2 | 300.0 | 2,727.90 | 1,363.95 | 7.23 |

### 4.5 Top directors (by total revenue)

| Director | Movies | Total revenue | Mean rating |
|----------|--------|---------------|-------------|
| James Cameron | 2 | 5,187.87 | 7.76 |
| Anthony Russo | 2 | 4,990.98 | 8.25 |
| Joe Russo | 2 | 4,990.98 | 8.25 |
| Joss Whedon | 2 | 2,924.22 | 7.68 |
| Chris Buck | 2 | 2,727.90 | 7.23 |
| Jennifer Lee | 2 | 2,727.90 | 7.23 |

### 4.6 Charts

| Chart | Function in `src/visualize.py` | What it shows |
|-------|-------------------------------|---------------|
| `revenue_vs_budget.png` | `plot_revenue_vs_budget()` | Budget and revenue are only moderately related (r = 0.58) |
| `roi_by_genre.png` | `plot_roi_by_genre()` | Comedy and Romance have the highest average ROI; Action the lowest |
| `popularity_vs_rating.png` | `plot_popularity_vs_rating()` | Popular movies are also the best rated (r = 0.90) |
| `yearly_box_office.png` | `plot_yearly_box_office()` | 2015, 2018 and 2019 have the most revenue in the dataset |
| `franchise_vs_standalone.png` | `plot_franchise_vs_standalone()` | Franchises cost more; the two standalone films have a higher ROI |
| `top_10_revenue.png` | `plot_top_10_revenue()` | Avengers: Endgame and Avatar lead |

## 5. Conclusions

1. All 18 movies are $1B+ blockbusters, so the results describe top-performing films, not the whole market.
2. Spending more does not guarantee a better return: *Avatar* and *Titanic* have the best ROI, while the expensive *Star Wars: The Last Jedi* has the lowest.
3. Audience popularity and rating are strongly linked.
4. The Avengers is the strongest franchise by total revenue and rating.
5. The franchise vs standalone comparison is limited: only two standalone films, one of which is *Titanic*.

## 6. Limitations

- Only 18 movies, all very successful. Any conclusion about "success" is biased towards hits.
- TMDb popularity and vote counts change daily, so results depend on when the data was fetched.
- Revenue is not adjusted for inflation, which favors recent films.
- Spark is built for much larger data. Here it runs in local mode on a small dataset, so the focus is on using Spark correctly rather than on speed.

## 7. Scaling to the full catalogue

TMDb has about 1 million movies. Search and Discover cannot list them all (they stop at 500 pages), so a full run would:

1. Take the ID list from TMDb's daily ID export file instead of a fixed list.
2. Fetch details in parallel within TMDb's rate limit, saving results in many part files and keeping a list of finished IDs so a crash can resume.
3. Load all part files with `spark.read.json("data/raw/")`. The cleaning code already uses Spark column functions, so it works at this size.
4. Load the saved Parquet for the analysis instead of re-cleaning every run, raise `spark.sql.shuffle.partitions`, and sample the data before plotting scatter charts.