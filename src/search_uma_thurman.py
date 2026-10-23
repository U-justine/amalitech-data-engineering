# Find Uma Thurman movies directed by Quentin Tarantino, ranked by runtime.
def find_uma_thurman(df):
    mask = (
        df["cast"].str.contains("Uma Thurman", na=False) &
        df["director"].str.contains("Quentin Tarantino", na=False)
    )

    results = df[mask].sort_values("runtime")
    results.to_csv("data/processed/uma_thurman_search.csv", index=False)
    return results