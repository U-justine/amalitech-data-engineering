# Key Insights

In this project I analysed the 18 valid movies from the brief. The 19th ID, `0`, is not a real movie, and my pipeline handled it as a 404. All money values are in millions of USD. TMDb updates popularity and vote counts every day, so if you fetch the data again, some numbers may be slightly different from mine.

## 1. Every movie in my dataset is a blockbuster

The first thing I noticed is that all 18 movies earned over **$1.2 billion**. Together they made about **$30.6 billion** from **$3.8 billion** in budgets. Even the movie with the lowest profit, *Star Wars: The Last Jedi*, still made over **$1.0 billion** in profit. This means my dataset shows the very top of the box office, not typical films, and I kept that in mind for every result below.

## 2. A big budget does not guarantee the best return

- *Avengers: Endgame* had the highest budget ($356M) and the highest revenue ($2,939M).
- *Avatar* had the highest profit ($2,687M) and the highest ROI (12.3x).
- *Star Wars: The Last Jedi* had one of the biggest budgets ($300M) but the lowest ROI (4.5x).

When I measured the correlation between budget and revenue, I got 0.58, so they are only moderately related. Spending more helps, but it does not decide how well a movie performs.

## 3. Popular movies are also well rated

Popularity and rating moved closely together in my data, with a correlation of 0.90. *Avengers: Endgame* and *Avengers: Infinity War* are both among the most popular and share the highest rating (8.25). The Jurassic World films have the lowest ratings (6.5–6.7).

## 4. Franchises dominate, but the two standalone films hold their own

16 of my 18 movies belong to a franchise. The only standalone films are *Titanic* and *Beauty and the Beast*.

| | Franchise | Standalone |
|---|---|---|
| Movies | 16 | 2 |
| Mean revenue | $1,691M | $1,765M |
| Median ROI | 7.8x | 9.6x |
| Mean budget | $218M | $180M |
| Mean rating | 7.39 | 7.44 |

At first the standalone films look better on every measure. However, there are only two of them, and one is *Titanic*, so I do not treat this as strong evidence that standalone films do better in general.

## 5. The Avengers is the most successful franchise

*The Avengers Collection* stands out with 4 movies, **$7,915M** in total revenue and the highest mean rating (7.96). Star Wars and Jurassic Park come next, with 2 movies each.

## 6. James Cameron and the Russo brothers lead the directors

- **James Cameron**: 2 movies (*Avatar*, *Titanic*), $5,188M in total revenue.
- **Anthony and Joe Russo**: 2 movies (*Infinity War*, *Endgame*), $4,991M in total revenue and the highest mean rating (8.25).

The Russo brothers co-directed both of their films, so I counted each movie for both of them.

## 7. Box office peaks in 2015, 2018 and 2019

Each of these years has 3–4 movies in my dataset and $5.9–6.7 billion in revenue. This reflects which movies were in the brief's list, not the whole film industry.

## 8. The two searches find no movies

Neither search returned any movies. No movie in my dataset stars Bruce Willis or Uma Thurman, or is directed by Quentin Tarantino. To make sure this was not a bug in my code, I checked the full cast and crew of all 18 movies, and the names are not there.