import os
import pandas as pd
from dotenv import load_dotenv

# Make sure paths like data/ and figures/ work from the project folder
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Import functions to collect, clean, and save movie data
from src.fetch_movies import fetch_movies
from src.clean_movies import clean_dataframe, inspect_columns, add_metrics
from src.validate_clean_data import save_clean_data

# Import functions to explore and analyze the movies
from src.explore_movies import print_basic_info
from src.analyze_kpis import show_all_kpis
from src.compare_franchises import compare_franchise_vs_standalone
from src.analyze_franchises import analyze_franchise_performance
from src.analyze_directors import analyze_director_performance

# Import the two required searches
from src.search_bruce_willis import find_bruce_willis
from src.search_uma_thurman import find_uma_thurman

# Import the chart functions
from src.visualize import (
    plot_revenue_vs_budget,
    plot_roi_by_genre,
    plot_popularity_vs_rating,
    plot_yearly_box_office,
    plot_franchise_vs_standalone,
    plot_top_10_revenue,
)

# The 19 IDs from the assignment (ID 0 is not a real movie, it tests the 404 handling)
MOVIE_IDS = [
    0, 299534, 19995, 140607, 299536, 597, 135397,
    420818, 24428, 168259, 99861, 284054, 12445,
    181808, 330457, 351286, 109445, 321612, 260513
]

# Show full tables in the terminal
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)


# print a title between the steps
def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main():
    # load the API key from the .env file
    load_dotenv()
    api_key = os.getenv("TMDB_API_KEY")

    # stop with a clear message if there is no API key and no saved data to use
    if not api_key and not os.path.exists("data/raw/tmdb_movies_raw.json"):
        raise SystemExit("Error: set TMDB_API_KEY in your .env file first.")

    section("1. Fetch")
    movies = fetch_movies(MOVIE_IDS, api_key)
    print(f"Loaded {len(movies)} of {len(MOVIE_IDS)} movies.")

    section("2. Clean & Save")
    clean_df = clean_dataframe(movies)
    inspect_columns(clean_df)
    save_clean_data(clean_df)

    # add profit, ROI, franchise and year columns for the analysis
    df = add_metrics(clean_df)
    print_basic_info(df)

    section("3. Rankings")
    show_all_kpis(df)

    section("4. Searches & Comparison")
    print("Search 1 - Sci-Fi Action movies starring Bruce Willis:")
    print(find_bruce_willis(df))

    print("\nSearch 2 - Uma Thurman movies directed by Quentin Tarantino:")
    print(find_uma_thurman(df))

    print("\nFranchise vs Standalone:")
    print(compare_franchise_vs_standalone(df))

    section("5. Deep Dives")
    print("Top Franchises:")
    print(analyze_franchise_performance(df))

    print("\nTop Directors:")
    print(analyze_director_performance(df))

    section("6. Visualizations")
    plot_revenue_vs_budget(df)
    plot_roi_by_genre(df)
    plot_popularity_vs_rating(df)
    plot_yearly_box_office(df)
    plot_franchise_vs_standalone(df)
    plot_top_10_revenue(df)
    print("Charts saved in the figures folder.")


if __name__ == "__main__":
    main()