# Run the full TMDB movie analysis pipeline with PySpark.

import os
import logging

from dotenv import load_dotenv

from src.spark_session import get_spark
from src.fetch_movies import fetch_movies
from src.clean_movies import clean_dataframe, inspect_columns, add_metrics
from src.validate_clean_data import save_clean_data
from src.explore_movies import print_basic_info
from src.analyze_kpis import show_all_kpis
from src.search_bruce_willis import find_bruce_willis
from src.search_uma_thurman import find_uma_thurman
from src.compare_franchises import compare_franchise_vs_standalone
from src.analyze_franchises import analyze_franchise_performance
from src.analyze_directors import analyze_director_performance
from src import visualize as viz

# The 19 IDs from the assignment (ID 0 is not a real movie, it tests the 404 handling)
MOVIE_IDS = [
    0, 299534, 19995, 140607, 299536, 597, 135397,
    420818, 24428, 168259, 99861, 284054, 12445,
    181808, 330457, 351286, 109445, 321612, 260513,
]


# print a title between the steps
def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


# steps 1-2: get the movies from the API (or the saved file), clean them and save them
def fetch_and_clean(spark, api_key):
    section("1. Fetch")
    raw_df = fetch_movies(spark, MOVIE_IDS, api_key)

    section("2. Clean & Save")
    clean_df = clean_dataframe(raw_df)
    inspect_columns(clean_df)
    save_clean_data(spark, clean_df)
    clean_df.select("id", "title", "release_date", "budget_musd", "revenue_musd").show(5)
    return clean_df


# step 3: summary statistics, missing values, correlations
def explore(df):
    section("3. Explore")
    print_basic_info(df)


# step 4: the 10 KPI rankings
def kpis(df):
    section("4. KPIs")
    show_all_kpis(df)


# step 5: the two search queries from the brief
def searches(df):
    section("5. Searches")
    print("Search 1 - Sci-Fi Action movies with Bruce Willis:")
    find_bruce_willis(df).show(truncate=False)
    print("Search 2 - Uma Thurman movies directed by Quentin Tarantino:")
    find_uma_thurman(df).show(truncate=False)


# step 6: franchise vs standalone, top franchises, top directors
def franchises_and_directors(df):
    section("6. Franchises & Directors")
    comparison = compare_franchise_vs_standalone(df)
    comparison.show()
    analyze_franchise_performance(df).show(5, truncate=False)
    analyze_director_performance(df).show(5, truncate=False)
    return comparison  # reused by the franchise chart


# step 7: save all charts to figures/
def charts(df, comparison):
    section("7. Charts")
    viz.plot_revenue_vs_budget(df)
    viz.plot_roi_by_genre(df)
    viz.plot_popularity_vs_rating(df)
    viz.plot_yearly_box_office(df)
    viz.plot_franchise_vs_standalone(comparison)
    viz.plot_top_10_revenue(df)
    print("Charts saved to figures/")


def main():
    # run from the project folder so paths like data/ and figures/ work
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # load the API key from the .env file
    load_dotenv()
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        logging.warning("TMDB_API_KEY not set - only the saved raw file can be used")

    spark = get_spark()
    try:
        clean_df = fetch_and_clean(spark, api_key)

        # add profit, ROI, franchise and year columns; cached because every step reuses it
        df = add_metrics(clean_df).cache()

        explore(df)
        kpis(df)
        searches(df)
        comparison = franchises_and_directors(df)
        charts(df, comparison)
    finally:
        spark.stop()  # always shut Spark down, even if a step fails


if __name__ == "__main__":
    main()