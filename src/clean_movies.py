from pyspark.sql import functions as F

# Final column order from the assignment
FINAL_COLS = [
    "id", "title", "tagline", "release_date", "genres", "belongs_to_collection",
    "original_language", "budget_musd", "revenue_musd", "production_companies",
    "production_countries", "vote_count", "vote_average", "popularity", "runtime",
    "overview", "spoken_languages", "poster_path", "cast", "cast_size", "director",
    "crew_size",
]

# Text that means "no value"
PLACEHOLDERS = ["No Data", ""]


# join a list of objects into one string like "Action|Adventure" (empty list becomes null)
def join_names(col_name, key="name"):
    names = F.transform(F.col(col_name), lambda x: x[key])
    return F.when(F.size(col_name) > 0, F.concat_ws("|", names))


# get the names of all the directors of a movie (sorted, so co-directors always match)
def get_director():
    directors = F.filter(F.col("credits.crew"), lambda p: p["job"] == "Director")
    names = F.array_sort(F.transform(directors, lambda p: p["name"]))
    return F.when(F.size(names) > 0, F.concat_ws("|", names))


# show the most common values in each extracted column to spot anomalies (like value_counts)
def inspect_columns(df):
    for col in ["belongs_to_collection", "genres", "production_countries",
                "production_companies", "spoken_languages"]:
        print(f"\n--- {col} ---")
        # split "Action|Adventure" into separate rows before counting
        (df.select(F.explode(F.split(col, r"\|")).alias(col))
           .groupBy(col).count()
           .orderBy(F.desc("count"))
           .show(5, truncate=False))


# clean the raw movie data and prepare it for analysis
def clean_dataframe(df):
    print("Rows and columns before cleaning:", df.count(), len(df.columns))

    # 1. remove columns that are not needed
    df = df.drop("adult", "imdb_id", "original_title", "video", "homepage")

    # 2-3. turn the JSON columns into simple text
    df = (df
          .withColumn("belongs_to_collection", F.col("belongs_to_collection.name"))
          .withColumn("genres", join_names("genres"))
          .withColumn("production_companies", join_names("production_companies"))
          .withColumn("production_countries", join_names("production_countries"))
          .withColumn("spoken_languages", join_names("spoken_languages", "english_name")))

    # get cast, director and crew size from the credits
    df = (df
          .withColumn("cast", join_names("credits.cast"))
          .withColumn("cast_size", F.size("credits.cast"))
          .withColumn("director", get_director())
          .withColumn("crew_size", F.size("credits.crew"))
          .drop("credits"))

    # 5. convert columns to the right data types (try_cast turns bad values into null)
    for col in ["budget", "revenue", "popularity", "runtime", "vote_average"]:
        df = df.withColumn(col, F.col(col).try_cast("double"))
    for col in ["id", "vote_count"]:
        df = df.withColumn(col, F.col(col).try_cast("long"))
    df = df.withColumn("release_date", F.try_to_date("release_date", "yyyy-MM-dd"))

    # 6. a value of 0 means "unknown", so replace it with null
    for col in ["budget", "revenue", "runtime"]:
        df = df.withColumn(col, F.when(F.col(col) != 0, F.col(col)))

    # convert budget and revenue to millions of US dollars
    df = (df
          .withColumn("budget_musd", F.col("budget") / 1_000_000)
          .withColumn("revenue_musd", F.col("revenue") / 1_000_000))

    # a rating with 0 votes means nothing, so replace it with null
    df = df.withColumn(
        "vote_average", F.when(F.col("vote_count") > 0, F.col("vote_average")))

    # replace placeholder text with null
    for col in ["overview", "tagline"]:
        df = df.withColumn(col, F.when(~F.trim(F.col(col)).isin(PLACEHOLDERS), F.col(col)))

    # 7. remove duplicates and rows without an id or title
    df = df.dropDuplicates(["id"]).dropna(subset=["id", "title"])

    # 8. keep rows that have at least 10 values filled in
    df = df.dropna(thresh=10)

    # 9. keep only released movies, then drop the status column
    df = df.filter(F.col("status") == "Released").drop("status")

    # 10-11. put the columns in the required order
    # (Spark has no index to reset, so we sort by id to get a fixed, repeatable order)
    df = df.select(FINAL_COLS).orderBy("id")

    print("Rows and columns after cleaning:", df.count(), len(df.columns))
    return df


# add profit, ROI, franchise yes/no and release year for the analysis
def add_metrics(df):
    return (df
            .withColumn("profit_musd", F.col("revenue_musd") - F.col("budget_musd"))
            .withColumn("roi", F.col("revenue_musd") / F.col("budget_musd"))
            .withColumn("is_franchise", F.col("belongs_to_collection").isNotNull())
            .withColumn("release_year", F.year("release_date")))
