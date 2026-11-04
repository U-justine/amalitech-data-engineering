from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType
from pyspark.sql.window import Window


# Spark UDF: Return on Investment = revenue / budget (null if either value is missing)
@F.udf(returnType=DoubleType())
def roi_udf(revenue, budget):
    if revenue is None or budget is None or budget == 0:
        return None
    return float(revenue / budget)


# rank movies by a column, with optional filters for votes and budget
def rank_movies(df, column, ascending=False, top_n=5, min_votes=0, min_budget=0):
    # apply the filters the KPI needs
    if min_votes > 0:
        df = df.filter(F.col("vote_count") >= min_votes)
    if min_budget > 0:
        df = df.filter(F.col("budget_musd") >= min_budget)

    # skip movies with no value for this column
    df = df.filter(F.col(column).isNotNull())

    # number the movies 1, 2, 3... with a window function
    order = F.col(column).asc() if ascending else F.col(column).desc()
    window = Window.orderBy(order, F.col("title"))  # title breaks ties

    return (df.withColumn("rank", F.row_number().over(window))
              .filter(F.col("rank") <= top_n)
              .select("rank", "title", F.round(column, 2).alias(column)))


# build the 10 KPI rankings required by the assignment
def all_kpis(df):
    # add ROI with the Spark UDF
    df = df.withColumn("roi", roi_udf(F.col("revenue_musd"), F.col("budget_musd")))

    return {
        "Highest Revenue": rank_movies(df, "revenue_musd"),
        "Highest Budget": rank_movies(df, "budget_musd"),
        "Highest Profit": rank_movies(df, "profit_musd"),
        "Lowest Profit": rank_movies(df, "profit_musd", ascending=True),
        "Highest ROI (budget >= 10M)": rank_movies(df, "roi", min_budget=10),
        "Lowest ROI (budget >= 10M)": rank_movies(df, "roi", ascending=True, min_budget=10),
        "Most Voted": rank_movies(df, "vote_count"),
        "Highest Rated (>= 10 votes)": rank_movies(df, "vote_average", min_votes=10),
        "Lowest Rated (>= 10 votes)": rank_movies(df, "vote_average", ascending=True, min_votes=10),
        "Most Popular": rank_movies(df, "popularity"),
    }


# print all 10 KPI rankings
def show_all_kpis(df):
    try:
        from IPython import get_ipython
        from IPython.display import display, Markdown
        in_notebook = get_ipython() is not None and "IPKernelApp" in get_ipython().config
    except ImportError:
        in_notebook = False

    for name, ranking in all_kpis(df).items():
        if in_notebook:
            display(Markdown(f"#### {name}"))
            display(ranking.toPandas().set_index("rank"))  # only 5 rows
        else:
            print(f"\n{name}:")
            ranking.show(truncate=False)
