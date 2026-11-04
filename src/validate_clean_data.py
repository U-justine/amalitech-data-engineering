import os
from pyspark.sql import functions as F

from src.clean_movies import FINAL_COLS

PARQUET_PATH = "data/processed/tmdb_movies_clean.parquet"
CSV_PATH = "data/processed/tmdb_movies_clean.csv"


# save the cleaned data and check that the saved file is correct
def save_clean_data(spark, df):
    os.makedirs("data/processed", exist_ok=True)

    # Parquet keeps the data types (dates, numbers), so the analysis reads this one
    df.write.mode("overwrite").parquet(PARQUET_PATH)

    # one easy-to-open CSV file for people to look at (small data, so pandas is fine here)
    df.toPandas().to_csv(CSV_PATH, index=False)

    # read the file back and check it
    saved = spark.read.parquet(PARQUET_PATH)
    duplicates = saved.count() - saved.select("id").distinct().count()
    print("Saved cleaned data to:", PARQUET_PATH, "and", CSV_PATH)
    print("Rows and columns:", saved.count(), len(saved.columns))
    print("Columns in the right order:", saved.columns == FINAL_COLS)
    print("Duplicate ids:", duplicates)
    print("Missing titles:", saved.filter(F.col("title").isNull()).count())
