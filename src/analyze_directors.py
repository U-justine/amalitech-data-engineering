# find the most successful directors by number of movies, revenue and rating.
def analyze_director_performance(df):
    directors = df.groupby("director").agg(
        Total_Movies=("id", "count"),
        Total_Revenue=("revenue_musd", "sum"),
        Mean_Rating=("vote_average", "mean"),
    ).round(2)

    directors = directors.sort_values("Total_Revenue", ascending=False)
    directors.to_csv("data/processed/director_performance.csv")
    return directors
