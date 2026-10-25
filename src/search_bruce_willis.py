# Find Science Fiction Action movies starring Bruce Willis, best rated first.
def find_bruce_willis(df):
    is_scifi = df["genres"].str.contains("Science Fiction", na=False)
    is_action = df["genres"].str.contains("Action", na=False)
    has_bruce = df["cast"].str.contains("Bruce Willis", na=False)

    results = df[is_scifi & is_action & has_bruce]
    results = results.sort_values("vote_average", ascending=False)

    results.to_csv("data/processed/bruce_willis_search.csv", index=False)
    return results[["title", "genres", "vote_average"]]
