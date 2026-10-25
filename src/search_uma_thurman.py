# Find Uma Thurman movies directed by Quentin Tarantino, shortest first.
def find_uma_thurman(df):
    has_uma = df["cast"].str.contains("Uma Thurman", na=False)
    by_tarantino = df["director"].str.contains("Quentin Tarantino", na=False)

    results = df[has_uma & by_tarantino]
    results = results.sort_values("runtime", ascending=True)

    results.to_csv("data/processed/uma_thurman_search.csv", index=False)
    return results[["title", "director", "runtime"]]
