# TMDB Movie Data Analysis

An end-to-end data pipeline that fetches movie data from the **TMDb (The Movie Database) API**, cleans it with **Pandas**, and produces KPIs, rankings, search queries and visualizations for a set of 18 blockbuster films.

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

1. **Fetch** – Pulls details, credits and collection info for each movie ID from the TMDb API, with timeouts, retries and 404 handling.
2. **Clean** – Flattens nested JSON (genres, cast, crew, production companies, collections), converts budget/revenue to millions of USD, handles missing and zero values, and removes duplicates.
3. **Analyze** – Computes profit, ROI and franchise status, then ranks movies, franchises and directors.
4. **Search** – Runs the two required filtered queries:
   - Science Fiction Action movies starring **Bruce Willis**, sorted by rating.
   - Movies starring **Uma Thurman** and directed by **Quentin Tarantino**, sorted by runtime.
5. **Visualize** – Saves five charts to `figures/`.

## API Robustness

[`src/fetch_movies.py`](./src/fetch_movies.py) is built to handle a real, unreliable API:

- **10-second timeout** on every request.
- **3 retries** with exponential backoff on connection errors, timeouts and 5xx responses.
- **404 handling** – invalid IDs (e.g. `0`) are skipped and logged to [`data/raw/fetch_failures.json`](./data/raw/fetch_failures.json) instead of crashing the run.
- **Local caching** – raw responses are saved to `data/raw/`, so the pipeline can be re-run offline after the first fetch.

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
│   ├── fetch_movies.py             # API extraction, retries, caching
│   ├── clean_movies.py             # Cleaning and transformation
│   ├── validate_clean_data.py      # Validates and saves cleaned data
│   ├── explore_movies.py           # Basic EDA
│   ├── analyze_kpis.py             # KPI ranking function
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
| [`fetch_movies.py`](./src/fetch_movies.py) | Calls the TMDb API, retries on failure, caches raw data |
| [`clean_movies.py`](./src/clean_movies.py) | Flattens JSON, fixes types, converts units, drops bad rows |
| [`validate_clean_data.py`](./src/validate_clean_data.py) | Checks the cleaned frame and writes it to CSV |
| [`explore_movies.py`](./src/explore_movies.py) | `head()`, `describe()`, missing-value summary |
| [`analyze_kpis.py`](./src/analyze_kpis.py) | Reusable ranking function (revenue, budget, profit, ROI, rating, popularity) |
| [`search_bruce_willis.py`](./src/search_bruce_willis.py) | Sci-Fi Action + Bruce Willis query |
| [`search_uma_thurman.py`](./src/search_uma_thurman.py) | Uma Thurman + Quentin Tarantino query |
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
| Cleaned dataset | [`data/processed/tmdb_movies_clean.csv`](./data/processed/tmdb_movies_clean.csv) |
| Franchise analysis | [`data/processed/franchise_performance.csv`](./data/processed/franchise_performance.csv) |
| Director analysis | [`data/processed/director_performance.csv`](./data/processed/director_performance.csv) |
| Bruce Willis search results | [`data/processed/bruce_willis_search.csv`](./data/processed/bruce_willis_search.csv) |
| Uma Thurman search results | [`data/processed/uma_thurman_search.csv`](./data/processed/uma_thurman_search.csv) |

### Figures

| Chart | File |
|-------|------|
| Revenue vs Budget | [`revenue_vs_budget.png`](./figures/revenue_vs_budget.png) |
| Top 10 Movies by Revenue | [`top_10_revenue.png`](./figures/top_10_revenue.png) |
| ROI by Genre | [`roi_by_genre.png`](./figures/roi_by_genre.png) |
| Popularity vs Rating | [`popularity_vs_rating.png`](./figures/popularity_vs_rating.png) |
| Franchise vs Standalone | [`franchise_vs_standalone.png`](./figures/franchise_vs_standalone.png) |

---

## Notes

**Dataset size.** The assignment provides 19 movie IDs. ID `0` is not a valid TMDb movie and returns a 404, so it is logged to `fetch_failures.json` and the analysis runs on the remaining **18 movies**.

**Empty search results.** None of the 18 movies feature Bruce Willis or Uma Thurman. Both required searches are fully implemented exactly as specified and filter the dataset correctly — they return empty results because no movie in this subset matches. This is expected behaviour, not a bug. To confirm the logic works, run either function on a larger TMDb dataset that includes, for example, *Pulp Fiction* or *Armageddon*.

**Units.** Budget, revenue and profit are reported in **millions of USD**. ROI is calculated as `revenue / budget` and only for movies with a budget of at least $10M, to avoid misleading ratios from tiny or missing budgets.

---

## Dependencies

| Package | Used for |
|---------|----------|
| `requests` | TMDb API calls |
| `pandas` | Cleaning and analysis |
| `matplotlib` | Charts |
| `python-dotenv` | Loading the API key from `.env` |
| `jupyter` | Notebook environment |

Exact versions are pinned in [`requirements.txt`](./requirements.txt).

---

## Author

**Umutoni Justine**
