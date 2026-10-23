# TMDB Movie Analysis - What I Found

## What this project is about

I took 18 popular movies (Avengers, Avatar, Star Wars, Titanic, Frozen, etc.) 
and pulled their data from TMDb, an online movie database.

I looked at things like:
- How much each movie cost to make (budget)
- How much it earned (revenue)
- How well people rated it
- Who directed it
- Whether it was part of a franchise

Then I cleaned the data and answered some questions about it.

## How I did it

1. **Fetched the data** from TMDb using Python and the `requests` library.
   I saved it to a file so I didn't have to fetch again.

2. **Cleaned the data** with Pandas:
   - Nested data (like genres and cast) was messy, so I flattened it.
   - Some budgets were 0 (TMDb uses 0 to mean "unknown"), so I changed them to NaN.
   - I converted money to millions to make it easier to read.
   - I removed duplicates and kept only movies that were released.

3. **Added new columns** to help with the analysis:
   - Profit = revenue minus budget
   - ROI = revenue divided by budget
   - Is it part of a franchise?
   - What year did it come out?

4. **Ranked and compared** the movies: who earned the most, who 
   wasted the most money, who got the best ratings, etc.

5. **Made some charts** to see the patterns more clearly.

## What I found

### Money

- **Avengers: Endgame** earned the most ($2,927M).
- **Avatar** made the most profit ($2,687M) because it cost less than Endgame.
- **Avatar** also had the best ROI (12.3x), meaning it earned 12 times 
  what it cost.
- The **worst ROI** was **Star Wars: The Last Jedi** (4.4x). Still 
  profitable, but the smallest margin in this group.

### Ratings and popularity

- **Avengers: Infinity War** was both the highest-rated (8.2) and the 
  most popular movie in the dataset.
- **Jurassic World: Fallen Kingdom** had the lowest rating (6.5).
- **The Avengers** had the most votes (40,032).

### Search tests

The assignment required two specific searches:
- **Bruce Willis movies** (filtered by rating > 7)
- **Uma Thurman movies** directed by **Quentin Tarantino**

Both search functions are fully implemented in the `src/` folder. However, neither actor appears in the provided 19-movie blockbuster list, so both searches correctly return empty tables. This is expected behavior for this specific dataset.

### Franchises vs standalone movies

| | Standalone | Franchise |
|---|---|---|
| Number of movies | 2 | 16 |
| Average revenue | $1,765M | $1,691M |
| Median ROI | 9.62 | 7.84 |
| Average budget | $180M | $218M |
| Average rating | 7.44 | 7.39 |

**What this means:** The two groups look similar. But this comparison 
isn't really fair. There are only 2 standalone movies in the dataset, 
and both are *Titanic* and *Avatar*, two of the highest-grossing films 
of all time. So the average for standalone movies is inflated.

What we can say is that franchises spend more money on average, but 
they don't earn proportionally more. That's why their ROI is a bit lower.

### Best franchises

| Franchise | Movies | Total revenue |
|---|---|---|
| The Avengers Collection | 4 | $7,904M |
| Star Wars Collection | 2 | $3,403M |
| Jurassic Park Collection | 2 | $2,982M |
| Avatar Collection | 1 | $2,924M |
| Frozen Collection | 2 | $2,728M |

The **Avengers Collection** won by a lot: 4 films, nearly $8 billion 
in total revenue.

### Best directors

| Director | Movies | Total revenue |
|---|---|---|
| James Cameron | 2 | $5,188M |
| Anthony Russo | 2 | $4,980M |
| Joss Whedon | 2 | $2,924M |
| J.J. Abrams | 1 | $2,068M |

**James Cameron** made the most money thanks to *Avatar* and *Titanic*. 
**Anthony Russo** had the highest average rating (8.22) among directors 
with multiple movies.

## Charts I made

1. **Revenue vs Budget**: every movie is above the break-even line, 
   meaning they all made money. Budgets are similar ($150M to $400M), 
   but revenue varies a lot.
2. **Average ROI by Genre**: Action, Animation, and Family have the 
   lowest average ROI. Comedy, Romance, and Crime look higher, but each 
   of those only has one movie, so the numbers aren't reliable.
3. **Popularity vs Rating**: no strong relationship. A movie can be 
   popular without being well rated.
4. **Yearly Revenue**: revenue is highest in recent years because 
   bigger blockbusters came out then.
5. **Franchise vs Standalone**: the two bars are almost the same 
   height, which matches the table above.

## Limits of this analysis

- **Small sample.** Only 18 movies, and they're all blockbusters. 
  Any conclusion like "franchises make more money" doesn't apply to 
  movies in general.
- **No flops.** Every movie in this dataset was a hit. We can't 
  compare winners to losers.
- **Revenue is theatrical only.** TMDb doesn't include streaming, DVD, 
  merchandise, etc.
- **Some genres only have 1 movie.** That makes their averages useless 
  for comparison.

## What I learned

- **James Cameron** made the two most profitable movies in this dataset.
- **The Avengers franchise** is the biggest by every measure.
- **Franchises and standalones** perform about the same once you account 
  for how few standalones we have.
- **Popularity and rating** don't move together. Being popular doesn't 
  mean being loved.

## Files in this project

- `notebooks/analysis.ipynb`: the full workflow (fetch, clean, analyze, chart)
- `data/raw_movies.json`: raw data from the API (cached)
- `reports/insights.md`: this file