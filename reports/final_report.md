# Final Report: TMDB Movie Data Analysis

## 1. Methodology

### Data extraction
The pipeline requests `/movie/{id}?append_to_response=credits` from the TMDb API for the **19 IDs** in the brief.
ID `0` is invalid: it returns a 404, which is logged and recorded in `data/raw/fetch_failures.json`, leaving **18 movies**.

API robustness (`src/fetch_movies.py`):
- 10-second timeout on every request
- up to 3 attempts for timeouts, connection errors and server errors, waiting 2 s then 4 s
- a 404 is logged and skipped without retrying
- Python `logging` with timestamps and levels
- raw responses cached in `data/raw/` (delete `data/raw/tmdb_movies_raw.json` to fetch again)

### Cleaning (`src/clean_movies.py`)
All 11 steps of the brief, in order:
1. Dropped `adult`, `imdb_id`, `original_title`, `video`, `homepage`.
2–3. Flattened `belongs_to_collection`, `genres`, `spoken_languages`, `production_countries`, `production_companies` (`|`-separated); extracted the full cast, cast size, director(s) and crew size from `credits`.
4. Inspected every extracted column with `value_counts()`; no anomalies were found.
5. Converted numeric columns with `errors="coerce"` and `release_date` to datetime.
6. Replaced 0 budget/revenue/runtime with NaN, converted money to million USD, set `vote_average` to NaN where `vote_count = 0`, replaced placeholder text in `overview`/`tagline` with NaN.
7. Removed duplicate IDs and rows with no ID or title.
8. Kept rows with at least 10 non-NaN values.
9. Kept only `Released` movies and dropped `status`.
10–11. Reordered to the 22 required columns and reset the index.

The cleaned data is saved to `data/processed/tmdb_movies_clean.csv` (18 rows × 22 columns), and the saved file is
read back to check the column order and that there are no duplicate IDs.
Profit, ROI, franchise flag and release year are then added for analysis only.

### Analysis
- **EDA:** overview of types and missing values, summary statistics, genre and year counts, correlations.
- **KPIs:** one UDF, `rank_movies()`, produces all 10 rankings (ROI limited to budget ≥ $10M, ratings to ≥ 10 votes).
- **Searches:** filter the genres, full cast and director columns, then sort as the brief asks.
- **Franchise vs standalone, top franchises and top directors** with `groupby().agg()`. Co-directors are grouped as one team.

## 2. Results

### KPIs (top result for each)

| KPI | Movie | Value |
|---|---|---|
| Highest revenue | Avengers: Endgame | $2,939M |
| Highest budget | Avengers: Endgame | $356M |
| Highest profit | Avatar | $2,687M |
| Lowest profit | Star Wars: The Last Jedi | $1,034M |
| Highest ROI (budget ≥ $10M) | Avatar | 12.3× |
| Lowest ROI (budget ≥ $10M) | Star Wars: The Last Jedi | 4.4× |
| Most voted | The Avengers | 40,161 votes |
| Highest rated (≥ 10 votes) | Avengers: Endgame | 8.25 |
| Lowest rated (≥ 10 votes) | Jurassic World: Fallen Kingdom | 6.52 |
| Most popular | Avengers: Endgame | 88.15 |

### Required searches
- **Search 1** (Science Fiction + Action + Bruce Willis, by rating): **0 results**.
- **Search 2** (Uma Thurman + directed by Quentin Tarantino, by runtime): **0 results**.

Neither actor appears in the full cast of any of the 18 films, and Tarantino directed none of them, so empty
results are correct for this dataset.

### Franchise vs standalone

| | Franchise (16) | Standalone (2) |
|---|---|---|
| Mean revenue | $1,691M | $1,765M |
| Median ROI | 7.84 | 9.62 |
| Mean budget | $218M | $180M |
| Mean popularity | 37.73 | 40.67 |
| Mean rating | 7.39 | 7.44 |

### Top franchise and director
- **The Avengers Collection:** 4 films, $1,111M total budget, $7,915M total revenue, mean rating 7.96.
- **James Cameron:** 2 films, $5,188M total revenue. The **Russo brothers** have the highest mean rating (8.25).

## 3. Key findings and conclusions
- Bigger budgets do not mean better returns: budget and ROI are negatively correlated (≈ -0.4).
- Popularity and rating are strongly correlated (r ≈ 0.90).
- Franchises spend more on average, but the two standalone films have a higher median ROI and are slightly more popular.
- Yearly totals peak in 2015, 2018 and 2019, mostly because more films from the list were released in those years.

## 4. Limitations
- Only 18 hand-picked blockbusters, all of them hits, so the results describe this list, not the film industry.
- Only 2 standalone films, which makes that comparison weak.
- Several genres have only 1–2 films, so their ROI figures are unreliable.
- TMDb revenue covers theatrical box office only, and TMDb figures (votes, popularity) change over time.
  All numbers here come from the fetch on 25 October 2026; a new fetch can give slightly different values.
