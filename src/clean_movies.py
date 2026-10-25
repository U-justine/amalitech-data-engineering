import numpy as np
import pandas as pd

# Final column order from the assignment
FINAL_COLS = [
    "id", "title", "tagline", "release_date", "genres", "belongs_to_collection",
    "original_language", "budget_musd", "revenue_musd", "production_companies",
    "production_countries", "vote_count", "vote_average", "popularity", "runtime",
    "overview", "spoken_languages", "poster_path", "cast", "cast_size", "director",
    "crew_size",
]


# combine a list of names into one string like "Action|Adventure".
def join_names(items, key="name"):
    if not isinstance(items, list) or len(items) == 0:
        return np.nan
    return "|".join(item[key] for item in items)


# get the collection name, or NaN if the movie is not part of a franchise.
def get_collection(value):
    if isinstance(value, dict):
        return value["name"]
    return np.nan


# get the names of all the directors of a movie (sorted, so co-directors always match).
def get_director(credits):
    names = []
    for person in credits["crew"]:
        if person["job"] == "Director":
            names.append(person["name"])
    if len(names) == 0:
        return np.nan
    return "|".join(sorted(names))


# show the most common values in each extracted column to spot anomalies.
def inspect_columns(df):
    for col in ["belongs_to_collection", "genres", "production_countries",
                "production_companies", "spoken_languages"]:
        print(f"\n--- {col} ---")
        # split "Action|Adventure" into separate values before counting
        values = df[col].str.split("|").explode()
        print(values.value_counts().head(5))


# clean the raw movie data and prepare it for analysis.
def clean_dataframe(movies):
    df = pd.DataFrame(movies)
    print("Shape before cleaning:", df.shape)

    # 1. remove columns that are not needed.
    df = df.drop(columns=["adult", "imdb_id", "original_title", "video", "homepage"])

    # 2-3. turn the JSON columns into simple text.
    df["belongs_to_collection"] = df["belongs_to_collection"].apply(get_collection)
    df["genres"] = df["genres"].apply(join_names)
    df["production_companies"] = df["production_companies"].apply(join_names)
    df["production_countries"] = df["production_countries"].apply(join_names)
    df["spoken_languages"] = df["spoken_languages"].apply(join_names, key="english_name")

    # get cast, director and crew size from the credits.
    df["cast"] = df["credits"].apply(lambda c: join_names(c["cast"]))
    df["cast_size"] = df["credits"].apply(lambda c: len(c["cast"]))
    df["director"] = df["credits"].apply(get_director)
    df["crew_size"] = df["credits"].apply(lambda c: len(c["crew"]))
    df = df.drop(columns=["credits"])

    # 5. convert columns to the right data types.
    for col in ["budget", "revenue", "id", "popularity", "runtime", "vote_count", "vote_average"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")

    # 6. a value of 0 means "unknown", so replace it with NaN.
    for col in ["budget", "revenue", "runtime"]:
        df[col] = df[col].replace(0, np.nan)

    # convert budget and revenue to millions of US dollars.
    df["budget_musd"] = df["budget"] / 1_000_000
    df["revenue_musd"] = df["revenue"] / 1_000_000

    # a rating with 0 votes means nothing, so replace it with NaN.
    df.loc[df["vote_count"] == 0, "vote_average"] = np.nan

    # replace placeholder text with NaN.
    df["overview"] = df["overview"].replace(["No Data", ""], np.nan)
    df["tagline"] = df["tagline"].replace(["No Data", ""], np.nan)

    # 7. remove duplicates and rows without an id or title.
    df = df.drop_duplicates(subset="id")
    df = df.dropna(subset=["id", "title"])

    # 8. keep rows that have at least 10 values filled in.
    df = df.dropna(thresh=10)

    # 9. keep only released movies, then drop the status column.
    df = df[df["status"] == "Released"]
    df = df.drop(columns=["status"])

    # 10-11. put the columns in the required order and reset the index.
    df = df[FINAL_COLS]
    df = df.reset_index(drop=True)

    print("Shape after cleaning:", df.shape)
    return df


# add profit, ROI, franchise yes/no and release year for the analysis.
def add_metrics(df):
    df = df.copy()
    df["profit_musd"] = df["revenue_musd"] - df["budget_musd"]
    df["roi"] = df["revenue_musd"] / df["budget_musd"]
    df["is_franchise"] = df["belongs_to_collection"].notna()
    df["release_year"] = df["release_date"].dt.year
    return df
