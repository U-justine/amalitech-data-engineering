# rank movies based on the selected column and apply filters to get the results you need.
def rank_movies(df, column, ascending=False, top_n=10, min_votes=0, min_budget=0):
    temp = df.copy()
    temp = temp[temp["vote_count"] >= min_votes]
    temp = temp[temp["budget_musd"] >= min_budget]
    temp = temp.dropna(subset=[column])

    return temp.sort_values(column, ascending=ascending).head(top_n)[["title", column]]