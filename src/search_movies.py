# Reusable movie search used by the two required queries

import pandas as pd


def search_movies(df, genres=None, actor=None, director=None,
                  sort_by="vote_average", ascending=False):
    mask = pd.Series(True, index=df.index)

    def has(col, value):
        return df[col].fillna("").str.split("|").apply(lambda names: value in names)

    for genre in genres or []:
        mask &= has("genres", genre)
    if actor:
        mask &= has("cast", actor)
    if director:
        mask &= has("director", director)

    return df[mask].sort_values(sort_by, ascending=ascending).reset_index(drop=True)