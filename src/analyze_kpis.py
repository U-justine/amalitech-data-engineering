# rank movies by a column, with optional filters for votes and budget.
def rank_movies(df, column, ascending=False, top_n=5, min_votes=0, min_budget=0):
    temp = df.copy()

    if min_votes > 0:
        temp = temp[temp["vote_count"] >= min_votes]
    if min_budget > 0:
        temp = temp[temp["budget_musd"] >= min_budget]

    temp = temp.sort_values(column, ascending=ascending)
    return temp[["title", column]].head(top_n)


# print the 10 KPI rankings required by the assignment.
def show_all_kpis(df):
    print("Highest Revenue:\n", rank_movies(df, "revenue_musd"), "\n")
    print("Highest Budget:\n", rank_movies(df, "budget_musd"), "\n")
    print("Highest Profit:\n", rank_movies(df, "profit_musd"), "\n")
    print("Lowest Profit:\n", rank_movies(df, "profit_musd", ascending=True), "\n")
    print("Highest ROI (budget >= 10M):\n", rank_movies(df, "roi", min_budget=10), "\n")
    print("Lowest ROI (budget >= 10M):\n", rank_movies(df, "roi", ascending=True, min_budget=10), "\n")
    print("Most Voted:\n", rank_movies(df, "vote_count"), "\n")
    print("Highest Rated (>= 10 votes):\n", rank_movies(df, "vote_average", min_votes=10), "\n")
    print("Lowest Rated (>= 10 votes):\n", rank_movies(df, "vote_average", ascending=True, min_votes=10), "\n")
    print("Most Popular:\n", rank_movies(df, "popularity"), "\n")
