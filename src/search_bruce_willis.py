# Find Bruce Willis movies with a rating above 7, ranked by rating.
def find_bruce_willis(df):
    mask = (
        df["cast"].str.contains("Bruce Willis", na=False) &
        (df["vote_average"] > 7)
    )

    results = df[mask].sort_values("vote_average", ascending=False)
    results.to_csv("data/processed/bruce_willis_search.csv", index=False)
    return results