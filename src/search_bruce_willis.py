from pyspark.sql import functions as F

from src.save_results import save_csv


# find Science Fiction Action movies starring Bruce Willis, best rated first
def find_bruce_willis(df):
    # split "Action|Adventure" into a list so we match whole names only
    genres = F.split("genres", r"\|")
    cast = F.split("cast", r"\|")

    results = (df.filter(F.array_contains(genres, "Science Fiction"))
                 .filter(F.array_contains(genres, "Action"))
                 .filter(F.array_contains(cast, "Bruce Willis"))
                 .orderBy(F.desc("vote_average"))
                 .select("title", "genres", "vote_average"))

    save_csv(results, "bruce_willis_search.csv")
    return results
