import os
import matplotlib
import matplotlib.pyplot as plt
from adjustText import adjust_text
from pyspark.sql import functions as F

# Spark does the grouping; only the small result is turned into pandas for Matplotlib.


# save the current chart to the figures folder (and show it when running in a notebook)
def save_plot(filename):
    os.makedirs("figures", exist_ok=True)
    plt.tight_layout()
    plt.savefig(os.path.join("figures", filename), dpi=120)
    if "inline" in matplotlib.get_backend().lower():
        plt.show()
    plt.close()


# write the movie title next to each dot on a scatter chart
def label_dots(pdf, x_col, y_col):
    texts = [plt.text(row[x_col], row[y_col], row["title"], fontsize=8)
             for _, row in pdf.iterrows()]
    # move the labels apart so they do not overlap, with a thin line to their dot
    adjust_text(texts, arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))


# 1. Revenue vs Budget (scatter)
def plot_revenue_vs_budget(df):
    pdf = (df.select("title", "budget_musd", "revenue_musd")
             .dropna().toPandas())

    plt.figure(figsize=(11, 7))
    plt.scatter(pdf["budget_musd"], pdf["revenue_musd"], color="royalblue")
    label_dots(pdf, "budget_musd", "revenue_musd")
    plt.title("Revenue vs Budget")
    plt.xlabel("Budget (M USD)")
    plt.ylabel("Revenue (M USD)")
    plt.grid(alpha=0.3)
    save_plot("revenue_vs_budget.png")


# 2. Average ROI for each genre (bar chart)
def plot_roi_by_genre(df):
    # a movie with 3 genres is counted once in each genre
    pdf = (df.withColumn("genre", F.explode(F.split("genres", r"\|")))
             .groupBy("genre").agg(F.mean("roi").alias("roi"))
             .dropna().orderBy("roi").toPandas())

    plt.figure(figsize=(8, 5))
    bars = plt.barh(pdf["genre"], pdf["roi"], color="coral")
    plt.bar_label(bars, fmt="%.1fx", padding=3)  # show the ROI value on each bar
    plt.margins(x=0.1)  # leave space for the labels
    plt.title("Average ROI by Genre")
    plt.xlabel("Average ROI (Revenue / Budget)")
    plt.ylabel("Genre")
    plt.grid(axis="x", alpha=0.3)
    save_plot("roi_by_genre.png")


# 3. Popularity vs Rating (scatter)
def plot_popularity_vs_rating(df):
    pdf = (df.select("title", "vote_average", "popularity")
             .dropna().toPandas())

    plt.figure(figsize=(11, 7))
    plt.scatter(pdf["vote_average"], pdf["popularity"], color="darkcyan")
    label_dots(pdf, "vote_average", "popularity")
    plt.title("Popularity vs Rating")
    plt.xlabel("Average Rating (0-10)")
    plt.ylabel("Popularity Score")
    plt.grid(alpha=0.3)
    save_plot("popularity_vs_rating.png")


# 4. Total revenue for each release year (bar chart)
def plot_yearly_box_office(df):
    pdf = (df.dropna(subset=["release_year"])  # skip movies with no release date
             .groupBy("release_year")
             .agg(F.sum("revenue_musd").alias("revenue"))
             .orderBy("release_year").toPandas())

    plt.figure(figsize=(8, 5))
    # int first so the labels read "2015", not "2015.0"
    bars = plt.bar(pdf["release_year"].astype(int).astype(str), pdf["revenue"], color="royalblue")
    plt.bar_label(bars, fmt="%.0f", padding=3)  # show the total on each bar
    plt.margins(y=0.1)  # leave space for the labels
    plt.title("Yearly Box Office Revenue")
    plt.xlabel("Release Year")
    plt.ylabel("Total Revenue (M USD)")
    plt.grid(axis="y", alpha=0.3)
    save_plot("yearly_box_office.png")


# 5. Franchise vs standalone: mean revenue, mean budget, median ROI and mean rating side by side
def plot_franchise_vs_standalone(comp):
    pdf = comp.toPandas().set_index("type")
    metrics = [("mean_revenue", "Mean Revenue (M USD)"),
               ("mean_budget", "Mean Budget (M USD)"),
               ("median_roi", "Median ROI"),
               ("mean_rating", "Mean Rating")]

    fig, axes = plt.subplots(1, 4, figsize=(14, 4))
    for ax, (col, label) in zip(axes, metrics, strict=True):
        bars = ax.bar(pdf.index, pdf[col], color=["orange", "mediumpurple"])
        ax.bar_label(bars, fmt="%.1f", padding=3)  # show the value on each bar
        ax.margins(y=0.15)
        ax.set_title(label)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("Franchise vs Standalone Movies")
    save_plot("franchise_vs_standalone.png")


# 6. Top 10 movies by revenue (bar chart)
def plot_top_10_revenue(df):
    pdf = (df.select("title", "revenue_musd")
             .orderBy(F.desc("revenue_musd")).limit(10)
             .toPandas().iloc[::-1])  # reverse so the biggest bar is on top

    plt.figure(figsize=(8, 5))
    bars = plt.barh(pdf["title"], pdf["revenue_musd"], color="seagreen")
    plt.bar_label(bars, fmt="%.0f", padding=3)  # show the revenue on each bar
    plt.margins(x=0.1)  # leave space for the labels
    plt.title("Top 10 Movies by Revenue")
    plt.xlabel("Revenue (M USD)")
    plt.ylabel("Movie")
    plt.grid(axis="x", alpha=0.3)
    save_plot("top_10_revenue.png")