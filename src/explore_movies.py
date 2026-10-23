# display a quick overview of the movies and their main numerical statistics.
def print_basic_info(df):
    print("--- First 5 Movies ---")
    cols = ["title", "release_year", "budget_musd", "revenue_musd", "vote_average"]
    print(df[cols].head())

    print("\n--- Numeric Summary ---")
    cols = ["budget_musd", "revenue_musd", "runtime", "vote_average"]
    print(df[cols].describe().round(2))