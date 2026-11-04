from pyspark.sql import functions as F


# show a quick overview of the movies and their main numbers
def print_basic_info(df):
    print("--- First 5 Movies ---")
    df.select("title", "release_year", "budget_musd", "revenue_musd", "vote_average").show(5, truncate=False)

    print("--- Numeric Summary ---")
    df.select("budget_musd", "revenue_musd", "runtime", "vote_average", "popularity").describe().show()

    # count the nulls in every column
    print("--- Missing Values ---")
    df.select([F.count(F.when(F.col(c).isNull(), c)).alias(c) for c in df.columns]).show(vertical=True)

    print("--- Movies per Release Year ---")
    df.groupBy("release_year").count().orderBy("release_year").show(50)

    print("--- Franchise vs Standalone Count ---")
    df.groupBy("is_franchise").count().show()

    # how the main numbers move together (1 = same direction, -1 = opposite)
    print("--- Correlations ---")
    pairs = [("budget_musd", "revenue_musd"), ("vote_average", "popularity"),
             ("budget_musd", "vote_average"), ("revenue_musd", "popularity")]
    for a, b in pairs:
        print(f"{a} vs {b}: {df.stat.corr(a, b):.2f}")
