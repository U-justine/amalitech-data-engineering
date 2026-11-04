import os
import json
import time
import logging
import requests

# Raw data is saved twice:
# - JSON Lines (one movie per line): the format Spark reads best
# - normal JSON (one list, indented): easy for people to open and read
RAW_JSONL = "data/raw/tmdb_movies_raw.jsonl"
RAW_JSON = "data/raw/tmdb_movies_raw.json"
FAILURES_JSON = "data/raw/fetch_failures.json"

# Settings for API robustness
TIMEOUT = 10   # seconds to wait for an answer
RETRIES = 3    # how many times to try each movie

# Show log messages with the time and level (INFO, WARNING, ERROR)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logging.getLogger("matplotlib").setLevel(logging.WARNING)  # hide chart library messages
logger = logging.getLogger(__name__)


# Request one movie (with its cast and crew) from TMDb. Returns the movie, or None if it failed.
def fetch_movie(movie_id, api_key):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {"append_to_response": "credits"}
    headers = {}

    # TMDb has two kinds of keys: the long "Read Access Token" (starts with "eyJ")
    # goes in a header, the short "API Key" goes in the URL
    if api_key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        params["api_key"] = api_key

    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)

            # The movie was found
            if r.status_code == 200:
                return r.json()

            # The API key is wrong: retrying will not help, so stop the whole run
            if r.status_code == 401:
                raise SystemExit("Error 401: TMDb rejected the API key. Check TMDB_API_KEY in your .env file.")

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


# Call the API for every ID and save the answers to data/raw/ (skipped if the file already exists).
def download_movies(movie_ids, api_key):
    os.makedirs("data/raw", exist_ok=True)

    # reuse the saved file, unless it is empty (for example after a failed run)
    if os.path.exists(RAW_JSONL) and os.path.getsize(RAW_JSONL) > 0:
        logger.info("Using the saved file %s (delete it to fetch fresh data)", RAW_JSONL)
        return

    if not api_key or api_key == "your_api_key_here":
        raise SystemExit("Error: set TMDB_API_KEY in your .env file first.")

    movies, failed_ids = [], []
    for movie_id in movie_ids:
        movie = fetch_movie(movie_id, api_key)
        if movie is None:
            failed_ids.append(movie_id)
        else:
            movies.append(movie)
            logger.info("Fetched: %s", movie["title"])
        time.sleep(0.3)  # small pause so we do not overload the API

    logger.info("Fetched %s of %s movies", len(movies), len(movie_ids))

    # do not save an empty file, otherwise the next run would reuse it
    if not movies:
        raise SystemExit("Error: no movies were fetched, so nothing was saved.")

    # One movie per line (for Spark)
    with open(RAW_JSONL, "w", encoding="utf-8") as f:
        for movie in movies:
            f.write(json.dumps(movie) + "\n")

    # All movies in one readable list (for people)
    with open(RAW_JSON, "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=2)

    # Save the IDs that failed so they can be checked later
    with open(FAILURES_JSON, "w", encoding="utf-8") as f:
        json.dump(failed_ids, f)


# Fetch the movies (or reuse the saved file) and load them into a Spark DataFrame.
def fetch_movies(spark, movie_ids, api_key):
    download_movies(movie_ids, api_key)

    # Spark reads the nested JSON and works out the schema (structs and arrays) by itself
    df = spark.read.json(RAW_JSONL)
    logger.info("Loaded %s movies into Spark", df.count())
    return df
