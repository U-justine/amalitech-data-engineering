# i compare movie franchises by their budgets, revenue, and average ratings to see which ones perform best.
def analyze_franchise_performance(df):
    franchises = (
        df.dropna(subset=["belongs_to_collection"])
        .groupby("belongs_to_collection")
        .agg(
            Movies=("id", "count"),
            Total_Budget=("budget_musd", "sum"),
            Mean_Budget=("budget_musd", "mean"),
            Total_Revenue=("revenue_musd", "sum"),
            Mean_Revenue=("revenue_musd", "mean"),
            Mean_Rating=("vote_average", "mean")
        )
        .round(2)
        .sort_values("Total_Revenue", ascending=False)
    )

    franchises.to_csv("data/processed/franchise_performance.csv")
    return franchises