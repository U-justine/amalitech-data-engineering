from pyspark.sql import functions as F

from src.save_results import save_csv


# find Uma Thurman movies directed by Quentin Tarantino, shortest first
def find_uma_thurman(df):
    cast = F.split("cast", r"\|")
    directors = F.split("director", r"\|")

    results = (df.filter(F.array_contains(cast, "Uma Thurman"))
                 .filter(F.array_contains(directors, "Quentin Tarantino"))
                 .orderBy(F.asc("runtime"))
                 .select("title", "director", "runtime"))

    save_csv(results, "uma_thurman_search.csv")
    return results
