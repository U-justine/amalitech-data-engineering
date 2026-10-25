# TMDB Movie Data Analysis

An end-to-end data pipeline that fetches movie data from the **TMDb (The Movie Database) API**, cleans it with **Pandas**, and produces KPIs, rankings, search queries and visualizations for the 19 movie IDs in the brief (18 valid films; ID `0` is invalid and is handled as a 404).

## Quick Links

| What | Where |
|------|-------|
| Main notebook | [`notebooks/tmdb_movie_analysis.ipynb`](./notebooks/tmdb_movie_analysis.ipynb) |
| Pipeline entry point | [`main.py`](./main.py) |
| Source modules | [`src/`](./src/) |
| Cleaned dataset | [`data/processed/tmdb_movies_clean.csv`](./data/processed/tmdb_movies_clean.csv) |
| Charts | [`figures/`](./figures/) |
| Insights summary | [`reports/insights.md`](./reports/insights.md) |
| Final report | [`reports/final_report.md`](./reports/final_report.md) |

---

## Project Overview

The pipeline runs in five stages:

1. **Fetch** – Pulls details and credits for each movie ID from the TMDb API, with timeouts, retries, 404 handling and logging.
2. **Clean** – Follows all 11 cleaning steps in the brief: flattens nested JSON, converts budget/revenue to millions of USD, turns zeros, zero-vote ratings and placeholder text into `NaN`, removes duplicates, keeps released films and reorders the columns. The saved file is read back and checked.
3. **Explore & analyze** – EDA (summary stats, missing values, genre and year counts, correlations), all 10 KPI rankings via one reusable function, franchise vs standalone comparison, top franchises and directors.
4. **Search** – Runs the two required filtered queries:
   - Science Fiction **and** Action movies starring **Bruce Willis**, sorted by rating (highest first).
   - Movies starring **Uma Thurman** and directed by **Quentin Tarantino**, sorted by runtime (shortest first).
5. **Visualize** – Saves the five required charts plus a Top 10 revenue chart to `figures/`.

## API Robustness

[`src/fetch_movies.py`](./src/fetch_movies.py) is built to handle a real, unreliable API:

- **10-second timeout** on every request.
- **Up to 3 attempts** for each movie if the request times out, the connection fails or the server returns an error, waiting a little longer each time (2 s, then 4 s).
- **404 handling** – invalid IDs (e.g. `0`) are logged as a warning, skipped without retrying, and recorded in [`data/raw/fetch_failures.json`](./data/raw/fetch_failures.json) instead of crashing the run.
- **Logging** – uses Python's `logging` module with timestamps and levels instead of `print`.
- **Local caching** – raw responses are saved to `data/raw/`, so the pipeline can be re-run offline. Delete `data/raw/tmdb_movies_raw.json` to fetch fresh data.

---

## Project Structure

```text
tmdb-movie-analysis/
├── data/
│   ├── raw/                        # Raw API responses (JSON + CSV) and fetch_failures.json
│   └── processed/                  # Cleaned dataset and analysis outputs
├── figures/                        # Saved charts (PNG)
├── notebooks/
│   └── tmdb_movie_analysis.ipynb   # Main notebook (imports from src/)
├── reports/
│   ├── insights.md                 # Plain-English summary of findings
│   └── final_report.md             # Methodology and detailed results
├── src/
│   ├── __init__.py
│   ├── fetch_movies.py             # API extraction, retries, logging, caching
│   ├── clean_movies.py             # Cleaning and transformation
│   ├── validate_clean_data.py      # Saves and checks the cleaned data
│   ├── explore_movies.py           # Basic EDA
│   ├── analyze_kpis.py             # rank_movies() UDF + all 10 KPIs
│   ├── search_bruce_willis.py      # Search query 1
│   ├── search_uma_thurman.py       # Search query 2
│   ├── compare_franchises.py       # Franchise vs standalone comparison
│   ├── analyze_franchises.py       # Top franchises
│   ├── analyze_directors.py        # Top directors
│   └── visualize.py                # Chart generation
├── main.py                         # Runs the full pipeline
├── requirements.txt
├── .env                            # API key (not committed)
├── .gitignore
└── README.md
```

### Source modules

| Module | Purpose |
|--------|---------|
| [`fetch_movies.py`](./src/fetch_movies.py) | Calls the TMDb API, retries on failure, logs errors, caches raw data |
| [`clean_movies.py`](./src/clean_movies.py) | Cleaning steps 1–11, `value_counts()` inspection, derived metrics |
| [`validate_clean_data.py`](./src/validate_clean_data.py) | Writes the cleaned data to CSV and checks the saved file |
| [`explore_movies.py`](./src/explore_movies.py) | Summary stats, missing values, genre and year counts, correlations |
| [`analyze_kpis.py`](./src/analyze_kpis.py) | Reusable `rank_movies()` UDF and all 10 KPI rankings |
| [`search_bruce_willis.py`](./src/search_bruce_willis.py) | Search 1: Science Fiction + Action + Bruce Willis, by rating |
| [`search_uma_thurman.py`](./src/search_uma_thurman.py) | Search 2: Uma Thurman + Quentin Tarantino, by runtime |
| [`compare_franchises.py`](./src/compare_franchises.py) | Franchise vs standalone metrics |
| [`analyze_franchises.py`](./src/analyze_franchises.py) | Most successful franchises |
| [`analyze_directors.py`](./src/analyze_directors.py) | Most successful directors |
| [`visualize.py`](./src/visualize.py) | Builds and saves all charts |

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/tmdb-movie-analysis.git
cd tmdb-movie-analysis
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Add your TMDb API key

Create a `.env` file in the project root:

```env
TMDB_API_KEY=your_api_key_here
```

A free key is available at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api). The `.env` file is listed in `.gitignore` and is never committed.

### 4. Run the pipeline

**Option A – Terminal**

```bash
python main.py
```

**Option B – Jupyter Notebook**

```bash
jupyter notebook notebooks/tmdb_movie_analysis.ipynb
```

---

## Outputs

| Output | Location |
|--------|----------|
| Raw API cache and CSV | [`data/raw/`](./data/raw/) |
| Failed / invalid IDs log | [`data/raw/fetch_failures.json`](./data/raw/fetch_failures.json) |
| Cleaned dataset (22 columns, in the order from the brief) | [`data/processed/tmdb_movies_clean.csv`](./data/processed/tmdb_movies_clean.csv) |
| Franchise vs standalone | [`data/processed/franchise_vs_standalone.csv`](./data/processed/franchise_vs_standalone.csv) |
| Franchise analysis | [`data/processed/franchise_performance.csv`](./data/processed/franchise_performance.csv) |
| Director analysis | [`data/processed/director_performance.csv`](./data/processed/director_performance.csv) |
| Bruce Willis search results | [`data/processed/bruce_willis_search.csv`](./data/processed/bruce_willis_search.csv) |
| Uma Thurman search results | [`data/processed/uma_thurman_search.csv`](./data/processed/uma_thurman_search.csv) |

### Figures

| Chart | File |
|-------|------|
| Revenue vs Budget (required) | [`revenue_vs_budget.png`](./figures/revenue_vs_budget.png) |
| Average ROI by Genre (required) | [`roi_by_genre.png`](./figures/roi_by_genre.png) |
| Popularity vs Rating (required) | [`popularity_vs_rating.png`](./figures/popularity_vs_rating.png) |
| Yearly Box Office Revenue (required) | [`yearly_box_office.png`](./figures/yearly_box_office.png) |
| Franchise vs Standalone (required) | [`franchise_vs_standalone.png`](./figures/franchise_vs_standalone.png) |
| Top 10 Movies by Revenue | [`top_10_revenue.png`](./figures/top_10_revenue.png) |

---

## Notes

**Dataset size.** The assignment provides 19 movie IDs. ID `0` is not a valid TMDb movie and returns a 404, so it is logged to `fetch_failures.json` and the analysis runs on the remaining **18 movies**.

**Empty search results.** Both required searches are implemented exactly as specified and search the *full* cast and crew of every film. Neither Bruce Willis nor Uma Thurman appears in any of the 18 films, and none is directed by Quentin Tarantino, so both return 0 rows. This is the correct answer for this dataset. The notebook shows this check.

**Clean file vs analysis columns.** The saved clean CSV has exactly the 22 columns listed in the brief. Profit, ROI, franchise flag and release year are added afterwards for analysis only.

**Units.** Budget, revenue and profit are reported in **millions of USD**. ROI is calculated as `revenue / budget` and only for movies with a budget of at least $10M, to avoid misleading ratios from tiny or missing budgets.

---

## Dependencies

| Package | Used for |
|---------|----------|
| `requests` | TMDb API calls |
| `pandas` | Cleaning and analysis |
| `matplotlib` | Charts |
| `adjustText` | Keeps the movie names on scatter charts from overlapping |
| `python-dotenv` | Loading the API key from `.env` |
| `numpy` | Missing-value handling |
| `jupyter` | Notebook environment |

Minimum versions are listed in [`requirements.txt`](./requirements.txt).

---

## Author

**Umutoni Justine**
