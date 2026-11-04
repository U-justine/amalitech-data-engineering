from pyspark.sql import functions as F

from src.save_results import save_csv


# compare franchise movies with standalone movies
def compare_franchise_vs_standalone(df):
    comp = (df
            # show "Franchise" / "Standalone" instead of true / false
            .withColumn("type", F.when(F.col("is_franchise"), "Franchise").otherwise("Standalone"))
            .groupBy("type")
            .agg(F.count("id").alias("movies"),
                 F.round(F.mean("revenue_musd"), 2).alias("mean_revenue"),
                 F.round(F.median("roi"), 2).alias("median_roi"),
                 F.round(F.mean("budget_musd"), 2).alias("mean_budget"),
                 F.round(F.mean("popularity"), 2).alias("mean_popularity"),
                 F.round(F.mean("vote_average"), 2).alias("mean_rating"))
            .orderBy("type"))

    save_csv(comp, "franchise_vs_standalone.csv")
    return comp
