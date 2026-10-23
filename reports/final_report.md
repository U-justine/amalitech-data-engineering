# Final Report: TMDB Movie Data Analysis

## 1. Methodology
This project fetches data for 19 movie IDs (18 valid blockbusters plus one invalid ID `0` used to test 404 error handling) using the TMDb REST API. The pipeline is modularized into a `src` directory for maintainability.

Data cleaning involved:
- Flattening nested lists (genres, companies, countries).
- Extracting the top 5 cast members and the director from the `credits` endpoint.
- Treating `0` values for budget, revenue, and runtime as missing (`NaN`) since TMDb uses `0` to mean "unknown".
- Converting budgets and revenues to millions of USD.
- Filtering out unreleased movies and removing duplicates.

The API fetch module includes timeout, retry, and 404 logging to ensure robust data collection.

## 2. KPIs & Searches Implemented
The project successfully generated rankings for:
- Highest Revenue
- Highest Budget
- Highest/Lowest Profit
- Highest/Lowest ROI (filtered to budgets >= $10M)
- Most Voted
- Highest/Lowest Rated (filtered to >= 10 votes)
- Most Popular

Additionally, custom search functions for **Bruce Willis** and **Uma Thurman + Quentin Tarantino** were implemented as required. Because the provided 19-movie list contains exclusively modern blockbusters, neither actor appears in the dataset, resulting in empty (but fully functional) search outputs.

## 3. Key Findings
- **Highest Revenue:** *Avengers: Endgame* ($2,927M)
- **Highest ROI:** *Avatar* (12.3x)
- **Top Franchise:** The Avengers Collection ($7,904M total)
- **Top Director:** James Cameron ($5,188M total)
- **Franchises vs Standalone:** Franchises have a higher average budget ($218M vs $180M) but slightly lower median ROI (7.84 vs 9.62). However, this comparison is biased because only 2 standalone movies are in the dataset (both massive hits).

## 4. Limitations
- The sample size is only 18 movies, all of which are blockbusters. This means the insights cannot be generalized to the entire film industry.
- TMDb revenue only includes theatrical releases, not streaming or merchandising.
- Some genre averages are based on only 1 movie, making them statistically unreliable.