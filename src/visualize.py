import os
import matplotlib.pyplot as plt
from adjustText import adjust_text


# save the current chart to the figures folder and show it.
def save_plot(filename):
    os.makedirs("figures", exist_ok=True)
    plt.tight_layout()
    plt.savefig("figures/" + filename)
    plt.show()
    plt.close()


# write the movie title next to each dot on a scatter chart.
def label_dots(df, x_col, y_col):
    texts = []
    for _, row in df.iterrows():
        texts.append(plt.text(row[x_col], row[y_col], row["title"], fontsize=8))
    # move the labels apart so they do not overlap, with a thin line to their dot
    adjust_text(texts, arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))


# 1. Revenue vs Budget (scatter)
def plot_revenue_vs_budget(df):
    plt.figure(figsize=(11, 7))
    plt.scatter(df["budget_musd"], df["revenue_musd"], color="royalblue")
    label_dots(df, "budget_musd", "revenue_musd")
    plt.title("Revenue vs Budget")
    plt.xlabel("Budget (M USD)")
    plt.ylabel("Revenue (M USD)")
    plt.grid(alpha=0.3)
    save_plot("revenue_vs_budget.png")


# 2. Average ROI for each genre (bar chart)
def plot_roi_by_genre(df):
    # a movie with 3 genres is counted once in each genre
    genre_df = df.assign(genre=df["genres"].str.split("|")).explode("genre")
    roi = genre_df.groupby("genre")["roi"].mean().sort_values()

    plt.figure(figsize=(8, 5))
    bars = plt.barh(roi.index, roi.values, color="coral")
    plt.bar_label(bars, fmt="%.1fx", padding=3)  # show the ROI value on each bar
    plt.margins(x=0.1)  # leave space for the labels
    plt.title("Average ROI by Genre")
    plt.xlabel("Average ROI (Revenue / Budget)")
    plt.ylabel("Genre")
    plt.grid(axis="x", alpha=0.3)
    save_plot("roi_by_genre.png")


# 3. Popularity vs Rating (scatter)
def plot_popularity_vs_rating(df):
    plt.figure(figsize=(11, 7))
    plt.scatter(df["vote_average"], df["popularity"], color="darkcyan")
    label_dots(df, "vote_average", "popularity")
    plt.title("Popularity vs Rating")
    plt.xlabel("Average Rating (0-10)")
    plt.ylabel("Popularity Score")
    plt.grid(alpha=0.3)
    save_plot("popularity_vs_rating.png")


# 4. Total revenue for each release year (bar chart)
def plot_yearly_box_office(df):
    yearly = df.groupby("release_year")["revenue_musd"].sum()

    plt.figure(figsize=(8, 5))
    bars = plt.bar(yearly.index.astype(str), yearly.values, color="royalblue")
    plt.bar_label(bars, fmt="%.0f", padding=3)  # show the total on each bar
    plt.margins(y=0.1)  # leave space for the labels
    plt.title("Yearly Box Office Revenue")
    plt.xlabel("Release Year")
    plt.ylabel("Total Revenue (M USD)")
    plt.grid(axis="y", alpha=0.3)
    save_plot("yearly_box_office.png")


# 5. Average revenue of franchise vs standalone movies (bar chart)
def plot_franchise_vs_standalone(df):
    avg = df.groupby("is_franchise")["revenue_musd"].mean()
    avg = avg.rename(index={True: "Franchise", False: "Standalone"})

    plt.figure(figsize=(7, 4))
    bars = plt.bar(avg.index, avg.values, color=["orange", "mediumpurple"])
    plt.bar_label(bars, fmt="%.0f", padding=3)  # show the average on each bar
    plt.margins(y=0.1)  # leave space for the labels
    plt.title("Franchise vs Standalone Revenue")
    plt.xlabel("Movie Type")
    plt.ylabel("Average Revenue (M USD)")
    plt.grid(axis="y", alpha=0.3)
    save_plot("franchise_vs_standalone.png")


# 6. Top 10 movies by revenue (bar chart)
def plot_top_10_revenue(df):
    top10 = df.sort_values("revenue_musd").tail(10)

    plt.figure(figsize=(8, 5))
    bars = plt.barh(top10["title"], top10["revenue_musd"], color="seagreen")
    plt.bar_label(bars, fmt="%.0f", padding=3)  # show the revenue on each bar
    plt.margins(x=0.1)  # leave space for the labels
    plt.title("Top 10 Movies by Revenue")
    plt.xlabel("Revenue (M USD)")
    plt.ylabel("Movie")
    plt.grid(axis="x", alpha=0.3)
    save_plot("top_10_revenue.png")