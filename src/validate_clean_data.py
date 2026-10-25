import os
import pandas as pd

from src.clean_movies import FINAL_COLS

OUT_PATH = "data/processed/tmdb_movies_clean.csv"


# Save the cleaned movie data and check that the saved file is correct.
def save_clean_data(df):
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    # read the file back and check it
    saved = pd.read_csv(OUT_PATH)
    print("Saved cleaned data to:", OUT_PATH)
    print("Rows and columns:", saved.shape)
    print("Columns in the right order:", list(saved.columns) == FINAL_COLS)
    print("Duplicate ids:", saved["id"].duplicated().sum())
