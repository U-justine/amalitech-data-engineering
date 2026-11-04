from pyspark.sql import functions as F

from src.save_results import save_csv


# find the most successful franchises by budget, revenue and rating
def analyze_franchise_performance(df):
    franchises = (df
                  .filter(F.col("belongs_to_collection").isNotNull())
                  .groupBy("belongs_to_collection")
                  .agg(F.count("id").alias("movies"),
                       F.round(F.sum("budget_musd"), 2).alias("total_budget"),
                       F.round(F.mean("budget_musd"), 2).alias("mean_budget"),
                       F.round(F.sum("revenue_musd"), 2).alias("total_revenue"),
                       F.round(F.mean("revenue_musd"), 2).alias("mean_revenue"),
                       F.round(F.mean("vote_average"), 2).alias("mean_rating"))
                  .orderBy(F.desc("total_revenue")))

    save_csv(franchises, "franchise_performance.csv")
    return franchises
