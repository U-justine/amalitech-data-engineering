# I compared directors based on their total movie revenue, number of movies, and average ratings.
def analyze_director_performance(df):
    directors = (
        df.dropna(subset=["director"])
        .groupby("director")
        .agg(
            Total_Movies=("id", "count"),
            Total_Revenue=("revenue_musd", "sum"),
            Mean_Rating=("vote_average", "mean")
        )
        .round(2)
        .sort_values("Total_Revenue", ascending=False)
    )

    directors.to_csv("data/processed/director_performance.csv")
    return directors