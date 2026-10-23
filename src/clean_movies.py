
import numpy as np
import pandas as pd


# clean the raw movie data and prepare it for analysis.
def clean_dataframe(movies):
    df = pd.DataFrame(movies)

    # combine lists of names into one string so they are easier to analyze.
    def flatten(items, key="name"):
        if not isinstance(items, list) or len(items) == 0:
            return np.nan
        return "|".join(i[key] for i in items)

    df["genres"] = df["genres"].apply(flatten)
    df["production_companies"] = df["production_companies"].apply(flatten)
    df["production_countries"] = df["production_countries"].apply(flatten)
    df["spoken_languages"] = df["spoken_languages"].apply(
        lambda x: flatten(x, "english_name")
    )

    # combine the collection name for movies that belong to a franchise.
    df["belongs_to_collection"] = df["belongs_to_collection"].apply(
        lambda x: x["name"] if isinstance(x, dict) else np.nan
    )

    # get the five main cast members from each movie.
    def get_top_cast(credits):
        cast = sorted(credits.get("cast", []), key=lambda a: a.get("order", 999))
        return "|".join(a["name"] for a in cast[:5]) if cast else np.nan

    # find the director from the movie's crew information.
    def get_director(credits):
        for person in credits.get("crew", []):
            if person.get("job") == "Director":
                return person["name"]
        return np.nan

    # extract cast, director, and crew details before removing the original credits data.
    df["cast"] = df["credits"].apply(get_top_cast)
    df["cast_size"] = df["credits"].apply(lambda x: len(x.get("cast", [])))
    df["director"] = df["credits"].apply(get_director)
    df["crew_size"] = df["credits"].apply(lambda x: len(x.get("crew", [])))
    df = df.drop(columns=["credits"])

    # remove columns that are not needed for this analysis.
    drop_cols = ["adult", "imdb_id", "original_title", "video", "homepage"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    # convert numeric fields and release dates into the correct data types.
    for col in ["budget", "revenue", "id", "popularity", "runtime", "vote_count", "vote_average"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")

    # treat zero budgets, revenues, and runtimes as missing values.
    for col in ["budget", "revenue", "runtime"]:
        df.loc[df[col] == 0, col] = np.nan

    # convert budget and revenue into millions of US dollars.
    df["budget_musd"] = df["budget"] / 1_000_000
    df["revenue_musd"] = df["revenue"] / 1_000_000
    df = df.drop(columns=["budget", "revenue"])

    # remove duplicate movies and records missing essential information.
    df = df.drop_duplicates("id").dropna(subset=["id", "title"])
    df = df[df.notna().sum(axis=1) >= 10]

    # keep only released movies and reset the row index.
    df = df[df["status"] == "Released"].drop(columns=["status"])
    df = df.reset_index(drop=True)

    # calculate profit, return on investment, franchise status, and release year.
    df["profit_musd"] = df["revenue_musd"] - df["budget_musd"]
    df["roi"] = df["revenue_musd"] / df["budget_musd"]
    df["is_franchise"] = df["belongs_to_collection"].notna()
    df["release_year"] = df["release_date"].dt.year

    return df
