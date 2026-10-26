import os
import json
import time
import logging
import requests
import pandas as pd

RAW_JSON = "data/raw/tmdb_movies_raw.json"
RAW_CSV = "data/raw/tmdb_movies_raw.csv"
FAILURES_JSON = "data/raw/fetch_failures.json"

# Settings for API robustness
TIMEOUT = 10   # seconds to wait for an answer
RETRIES = 3    # how many times to try each movie

# Show log messages with the time and level (INFO, WARNING, ERROR)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logging.getLogger("matplotlib").setLevel(logging.WARNING)  # hide chart library messages
logger = logging.getLogger(__name__)


# Request one movie from TMDb. Returns the movie, or None if it failed.
def fetch_movie(movie_id, api_key):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {"api_key": api_key, "append_to_response": "credits"}

    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)

            # The movie was found
            if r.status_code == 200:
                return r.json()

            # The movie does not exist (for example ID 0), so do not retry
            if r.status_code == 404:
                logger.warning("Movie %s not found (404), skipping", movie_id)
                return None

            # Any other error: log it and try again
            logger.warning("Movie %s: status %s (attempt %s/%s)", movie_id, r.status_code, attempt, RETRIES)

        except requests.exceptions.RequestException as e:
            # Timeout or connection problem: log it and try again
            logger.warning("Movie %s: %s (attempt %s/%s)", movie_id, e, attempt, RETRIES)

        # Wait a bit longer before the next attempt (2s, then 4s)
        if attempt < RETRIES:
            time.sleep(2 * attempt)

    logger.error("Movie %s failed after %s attempts", movie_id, RETRIES)
    return None


# Fetch all movies from TMDb and save them for later use.
def fetch_movies(movie_ids, api_key):
    os.makedirs("data/raw", exist_ok=True)

    # Reuse the saved data if it is already available.
    if os.path.exists(RAW_JSON):
        logger.info("Loading movies from the saved file %s", RAW_JSON)
        with open(RAW_JSON, "r", encoding="utf-8") as f:
            return json.load(f)

    movies = []
    failed_ids = []

    for movie_id in movie_ids:
        movie = fetch_movie(movie_id, api_key)
        if movie is None:
            failed_ids.append(movie_id)
        else:
            movies.append(movie)
            logger.info("Fetched: %s", movie["title"])
        time.sleep(0.3)  # small pause so we do not overload the API

    logger.info("Fetched %s of %s movies", len(movies), len(movie_ids))

    # Save the original API data as JSON and CSV.
    with open(RAW_JSON, "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=2)
    pd.DataFrame(movies).to_csv(RAW_CSV, index=False)

    # Save the IDs that failed so they can be checked later.
    with open(FAILURES_JSON, "w", encoding="utf-8") as f:
        json.dump(failed_ids, f)

    return movies