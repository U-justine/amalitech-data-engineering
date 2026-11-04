import os


# save a small Spark result as one CSV file in data/processed/
def save_csv(df, filename):
    os.makedirs("data/processed", exist_ok=True)
    df.toPandas().to_csv(os.path.join("data/processed", filename), index=False)
