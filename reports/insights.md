# TMDB Movie Analysis - What I Found

## What this project is about

I took the 19 movie IDs from the brief and pulled their data from TMDb, an online movie database.
One ID (`0`) is not a real movie, so the API returned a 404. My code logged it and kept going,
which left **18 movies** (Avengers, Avatar, Star Wars, Titanic, Frozen, etc.).

I looked at:
- How much each movie cost to make (budget)
- How much it earned (revenue)
- How well people rated it and how popular it is
- Who directed it
- Whether it was part of a franchise

## How I did it

1. **Fetched the data** from TMDb with `requests`. Every request has a timeout, failed requests are
   retried with increasing waits, and a 404 is logged and skipped. I cached the results so I didn't
   have to fetch again.

2. **Cleaned the data** with Pandas, following the brief step by step:
   - Flattened the nested columns (genres, collection, companies, countries, languages) into text like `Action|Adventure`.
   - Took the full cast list and the director(s) from the credits.
   - Changed budgets, revenues and runtimes of 0 to NaN (TMDb uses 0 for "unknown").
   - Converted money to millions of USD.
   - Set the rating to NaN for any movie with 0 votes and replaced placeholder text like "No Data" with NaN.
   - Removed duplicates, kept only released movies and put the columns in the order from the brief.
   - Checked the saved file to make sure it really is the cleaned data.

3. **Added new columns** for the analysis: profit, ROI (revenue ÷ budget), franchise or not, and release year.

4. **Explored, ranked and compared** the movies, then **made charts** to see the patterns.

## What I found

### Money

- **Avengers: Endgame** earned the most ($2,939M).
- **Avatar** made the most profit ($2,687M) because it cost much less than Endgame ($237M vs $356M).
- **Avatar** also had the best ROI (12.3x), meaning it earned 12 times what it cost.
- The **worst ROI** was **Star Wars: The Last Jedi** (4.4x). Still very profitable, but the smallest return in this group.
- Every movie made at least $1.2 billion, so there are no flops in this list.

### Ratings and popularity

- **Avengers: Endgame** is the highest rated (8.247) and the most popular, just ahead of
  **Avengers: Infinity War** (8.246).
- **Jurassic World: Fallen Kingdom** had the lowest rating (6.52).
- **The Avengers** has the most votes (40,161).
- Popularity and rating move together strongly here (correlation 0.90): the best-rated films are also the most popular.

### The two required searches

- **Search 1:** Science Fiction **and** Action movies starring **Bruce Willis**, best rated first.
- **Search 2:** Movies starring **Uma Thurman** and directed by **Quentin Tarantino**, shortest first.

Both return **no movies**. I checked the full cast and crew of all 18 films: Bruce Willis and Uma Thurman
are not in any of them, and Tarantino didn't direct any. So an empty result is the correct answer for this list.

### Franchises vs standalone movies

| | Franchise | Standalone |
|---|---|---|
| Number of movies | 16 | 2 |
| Average revenue | $1,691M | $1,765M |
| Median ROI | 7.84 | 9.62 |
| Average budget | $218M | $180M |
| Average popularity | 37.73 | 40.67 |
| Average rating | 7.39 | 7.44 |

**What this means:** franchises spend more on average, but they are not more popular and they don't earn
proportionally more, so their ROI is lower. This comparison isn't really fair, though: there are only
2 standalone movies (*Titanic* and *Beauty and the Beast*), and *Titanic* is one of the highest-grossing films ever.

### Best franchises

| Franchise | Movies | Total revenue | Mean rating |
|---|---|---|---|
| The Avengers Collection | 4 | $7,915M | 7.96 |
| Star Wars Collection | 2 | $3,403M | 6.98 |
| Jurassic Park Collection | 2 | $2,982M | 6.61 |
| Avatar Collection | 1 | $2,924M | 7.61 |
| Frozen Collection | 2 | $2,728M | 7.23 |

The **Avengers Collection** won by a lot: 4 films, nearly $8 billion in total revenue.

### Best directors

| Director | Movies | Total revenue | Mean rating |
|---|---|---|---|
| James Cameron | 2 | $5,188M | 7.76 |
| Anthony Russo, Joe Russo | 2 | $4,991M | 8.25 |
| Joss Whedon | 2 | $2,924M | 7.68 |
| Chris Buck, Jennifer Lee | 2 | $2,728M | 7.23 |
| J.J. Abrams | 1 | $2,068M | 7.24 |

**James Cameron** made the most money thanks to *Avatar* and *Titanic*. The **Russo brothers** have the
highest average rating (8.25). I kept co-directors together as one team so their revenue isn't counted twice.

## Charts I made

1. **Revenue vs Budget:** every movie earned far more than it cost. Budgets are similar ($125M to $356M),
   but revenue varies a lot ($1.2B to $2.9B).
2. **Average ROI by Genre:** Action, Animation and Family have the lowest average ROI (about 7.4–7.7x).
   Comedy and Romance look the highest, but they have only 1 or 2 movies each, so those numbers aren't reliable.
3. **Popularity vs Rating:** a strong positive relationship (r = 0.90).
4. **Yearly Box Office Revenue:** 2015, 2018 and 2019 have the highest totals, mainly because 3–4 films
   from the list came out in each of those years.
5. **Franchise vs Standalone:** average revenue is almost the same for both groups.

I also made a Top 10 revenue chart.

## Limits of this analysis

- **Small sample.** Only 18 movies, and they're all blockbusters. A conclusion like "franchises make more money" doesn't apply to movies in general.
- **No flops.** Every movie in this dataset was a hit, so we can't compare winners to losers.
- **Only 2 standalone films**, which makes the franchise comparison weak.
- **Revenue is theatrical only.** TMDb doesn't include streaming, DVD or merchandise.
- **TMDb numbers change** (votes, popularity, sometimes revenue). All numbers here come from the fetch on
  25 October 2026, so re-fetching later can give slightly different results.

## What I learned

- **James Cameron's** two films, *Avatar* and *Titanic*, are both in the top 3 for profit and ROI.
- **The Avengers franchise** is the biggest by revenue and has the most-voted and most popular films.
- **Spending more doesn't mean a better return:** budget is negatively correlated with ROI (about -0.4).
- **Popularity and rating go together** in this set of films.

## Files in this project

- `notebooks/tmdb_movie_analysis.ipynb`: the full workflow with outputs (fetch, clean, explore, analyze, chart)
- `main.py`: runs the whole pipeline from the terminal
- `src/`: all the reusable code
- `data/raw/`: raw API data (cached) and `fetch_failures.json`
- `data/processed/tmdb_movies_clean.csv`: the cleaned dataset
- `figures/`: all charts
- `reports/final_report.md`: methodology and results
