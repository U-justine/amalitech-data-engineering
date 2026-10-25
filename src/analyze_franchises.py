# find the most successful franchises by budget, revenue and rating.
def analyze_franchise_performance(df):
    franchises = df.groupby("belongs_to_collection").agg(
        Movies=("id", "count"),
        Total_Budget=("budget_musd", "sum"),
        Mean_Budget=("budget_musd", "mean"),
        Total_Revenue=("revenue_musd", "sum"),
        Mean_Revenue=("revenue_musd", "mean"),
        Mean_Rating=("vote_average", "mean"),
    ).round(2)

    franchises = franchises.sort_values("Total_Revenue", ascending=False)
    franchises.to_csv("data/processed/franchise_performance.csv")
    return franchises
