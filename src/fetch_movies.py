import os
import json
import time
import requests
import pandas as pd

RAW_DIR = "data/raw"
RAW_JSON = os.path.join(RAW_DIR, "tmdb_movies_raw.json")
RAW_CSV = os.path.join(RAW_DIR, "tmdb_movies_raw.csv")

# Settings for API robustness
TIMEOUT = 10
RETRIES = 3


# Save the raw movie data as a CSV file before cleaning.
def save_raw_csv(movies):
    df_raw = pd.DataFrame(movies)
    df_raw.to_csv(RAW_CSV, index=False)
    print(f"Saved raw data to: {RAW_CSV}")
    print(f"Raw shape: {df_raw.shape[0]} rows x {df_raw.shape[1]} columns")
    return df_raw


# Fetch movie details from TMDb and save them for later use.
def fetch_movies(movie_ids, api_key):
    os.makedirs(RAW_DIR, exist_ok=True)

    # Reuse the saved data if it is already available.
    if os.path.exists(RAW_JSON):
        print("Loading from raw cache...")
        with open(RAW_JSON, "r") as f:
            movies = json.load(f)
        save_raw_csv(movies)
        return movies

    movies = []
    failures = []

    # Request each movie's details, including cast and crew.
    for mid in movie_ids:
        url = f"https://api.themoviedb.org/3/movie/{mid}"
        params = {"api_key": api_key, "append_to_response": "credits"}
        
        # Robust API request: timeout + retries
        response = None
        for attempt in range(1, RETRIES + 1):
            try:
                r = requests.get(url, params=params, timeout=TIMEOUT)
                
                # Handle 404 (e.g., ID 0) immediately without retrying
                if r.status_code == 404:
                    print(f"Failed: {mid} (Status: 404 Not Found)")
                    failures.append({"id": mid, "status": 404})
                    response = None
                    break
                
                # Check for other HTTP errors
                r.raise_for_status()
                response = r
                break  # Success!
                
            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt}/{RETRIES} failed for {mid}: {e}")
                if attempt < RETRIES:
                    time.sleep(2) # Wait 2 seconds before retrying
        
        # Process successful response
        if response is not None:
            movies.append(response.json())
            print(f"Fetched: {response.json()['title']}")

        time.sleep(0.3)

    # Save the original API responses as JSON.
    with open(RAW_JSON, "w") as f:
        json.dump(movies, f, indent=2)

    # Save failed requests so they can be checked later.
    if failures:
        with open(os.path.join(RAW_DIR, "fetch_failures.json"), "w") as f:
            json.dump(failures, f, indent=2)

    save_raw_csv(movies)
    return movies