import os
import sys

from dotenv import load_dotenv

# Make sure paths like data/ and figures/ resolve from the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Import functions to collect, clean, and validate movie data
from src.fetch_movies import fetch_movies
from src.clean_movies import clean_dataframe
from src.validate_clean_data import save_clean_data

# Import functions to explore the dataset and analyze movie performance
from src.explore_movies import print_basic_info
from src.analyze_kpis import rank_movies
from src.compare_franchises import compare_franchise_vs_standalone
from src.analyze_franchises import analyze_franchise_performance
from src.analyze_directors import analyze_director_performance

# Import functions to find movies featuring specific actors (Required searches)
from src.search_bruce_willis import find_bruce_willis
from src.search_uma_thurman import find_uma_thurman

# Import functions to create charts and visualize movie trends
from src.visualize import (
    plot_revenue_vs_budget,
    plot_top_10_revenue,
    plot_roi_by_genre,
    plot_popularity_vs_rating,
    plot_franchise_vs_standalone,
)

# The exact 19 IDs provided in the assignment (including 0 to test 404 handling)
MOVIE_IDS = [
    0, 299534, 19995, 140607, 299536, 597, 135397,
    420818, 24428, 168259, 99861, 284054, 12445,
    181808, 330457, 351286, 109445, 321612, 260513
]


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main():
    load_dotenv()
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key or api_key == "your_actual_api_key_here":
        sys.exit("Error: set TMDB_API_KEY in your .env file first.")

    section("1. Fetch")
    try:
        raw_movies = fetch_movies(MOVIE_IDS, api_key)
        print(f"Loaded {len(raw_movies)} movies.")
    except RuntimeError as e:
        print(f"Fetch failed: {e}")
        raw_movies = []

    section("2. Clean & Save")
    df = clean_dataframe(raw_movies)
    save_clean_data(df)
    print_basic_info(df)

    section("3. Rankings")
    print("Top 5 Revenue:")
    print(rank_movies(df, "revenue_musd", top_n=5).to_string(index=False))
    print("\nTop 5 ROI (Budget >= $10M):")
    print(rank_movies(df, "roi", top_n=5, min_budget=10).to_string(index=False))

    section("4. Searches & Comparison")
    print("Bruce Willis movies:")
    print(find_bruce_willis(df)[["title", "vote_average"]].to_string(index=False))
    
    print("\nUma Thurman + Quentin Tarantino:")
    print(find_uma_thurman(df)[["title", "runtime"]].to_string(index=False))
    
    print("\nFranchise vs Standalone:")
    print(compare_franchise_vs_standalone(df))

    section("5. Deep Dives")
    print("Top Franchises by Revenue:")
    print(analyze_franchise_performance(df).head(10))
    
    print("\nTop Directors by Revenue:")
    print(analyze_director_performance(df).head(10))

    section("6. Visualizations")
    print("Saving charts to figures/ (close each chart window to continue)...")
    plot_revenue_vs_budget(df)
    plot_top_10_revenue(df)
    plot_roi_by_genre(df)
    plot_popularity_vs_rating(df)
    plot_franchise_vs_standalone(df)

    section("Done")
    print("Outputs: data/raw/, data/processed/, figures/")


if __name__ == "__main__":
    main()