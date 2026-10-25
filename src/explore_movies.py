# display a quick overview of the movies and their main numbers.
def print_basic_info(df):
    print("--- First 5 Movies ---")
    print(df[["title", "release_year", "budget_musd", "revenue_musd", "vote_average"]].head())

    print("\n--- Numeric Summary ---")
    print(df[["budget_musd", "revenue_musd", "runtime", "vote_average", "popularity"]].describe().round(2))

    print("\n--- Missing Values ---")
    print(df.isna().sum())

    print("\n--- Movies per Release Year ---")
    print(df["release_year"].value_counts().sort_index())

    print("\n--- Franchise vs Standalone Count ---")
    print(df["is_franchise"].value_counts())

    # show how the main numbers move together (1 = same direction, -1 = opposite)
    print("\n--- Correlations ---")
    print(df[["budget_musd", "revenue_musd", "roi", "vote_average", "popularity"]].corr().round(2))
