# compare franchise movies with standalone movies.
def compare_franchise_vs_standalone(df):
    comp = df.groupby("is_franchise").agg(
        Movies=("id", "count"),
        Mean_Revenue=("revenue_musd", "mean"),
        Median_ROI=("roi", "median"),
        Mean_Budget=("budget_musd", "mean"),
        Mean_Popularity=("popularity", "mean"),
        Mean_Rating=("vote_average", "mean"),
    ).round(2)

    # show "Franchise" / "Standalone" instead of True / False
    comp = comp.rename(index={True: "Franchise", False: "Standalone"})

    comp.to_csv("data/processed/franchise_vs_standalone.csv")
    return comp
