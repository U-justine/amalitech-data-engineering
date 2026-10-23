import os


# Save the cleaned movie data so it can be used for analysis.
def save_clean_data(df):
    out_dir = "data/processed"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "tmdb_movies_clean.csv")

    df.to_csv(out_path, index=False)
    print(f"Saved cleaned data to: {out_path}")
    print(f"Total movies: {len(df)}")