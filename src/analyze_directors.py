from pyspark.sql import functions as F

from src.save_results import save_csv


# find the most successful directors by number of movies, revenue and rating
def analyze_director_performance(df):
    directors = (df
                 # a movie with two directors counts for each of them
                 .withColumn("director", F.explode(F.split("director", r"\|")))
                 .groupBy("director")
                 .agg(F.count("id").alias("total_movies"),
                      F.round(F.sum("revenue_musd"), 2).alias("total_revenue"),
                      F.round(F.mean("vote_average"), 2).alias("mean_rating"))
                 .orderBy(F.desc("total_revenue")))

    save_csv(directors, "director_performance.csv")
    return directors
