# compare the financial performance and audience response of franchise and standalone movies.
def compare_franchise_vs_standalone(df):
    comp = df.groupby("is_franchise").agg(
        Movies=("id", "count"),
        Mean_Revenue=("revenue_musd", "mean"),
        Median_ROI=("roi", "median"),
        Mean_Budget=("budget_musd", "mean"),
        Mean_Popularity=("popularity", "mean"),
        Mean_Rating=("vote_average", "mean")
    ).round(2)

    comp.to_csv("data/processed/franchise_vs_standalone.csv")
    return comp