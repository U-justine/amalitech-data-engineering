
import os
import matplotlib.pyplot as plt

FIGURES_DIR = "figures"


def save_plot(filename):
    os.makedirs(FIGURES_DIR, exist_ok=True)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, filename), bbox_inches="tight")
    plt.show()


# Shows how movie budgets compare with the revenue they generate
def plot_revenue_vs_budget(df):
    plt.figure(figsize=(8, 5))
    plt.scatter(df["budget_musd"], df["revenue_musd"], color="royalblue", alpha=0.7)

    limit = max(df["budget_musd"].max(), df["revenue_musd"].max())
    plt.plot([0, limit], [0, limit], "r--", label="Break-even")

    plt.title("Movie Revenue vs Budget")
    plt.xlabel("Budget (M USD)")
    plt.ylabel("Revenue (M USD)")
    plt.legend()
    plt.grid(alpha=0.2)
    save_plot("revenue_vs_budget.png")


# Highlights the ten movies with the highest revenue
def plot_top_10_revenue(df):
    top10 = df.nlargest(10, "revenue_musd").sort_values("revenue_musd")

    plt.figure(figsize=(8, 5))
    plt.barh(top10["title"], top10["revenue_musd"], color="seagreen")

    plt.title("Top 10 Highest-Grossing Movies")
    plt.xlabel("Revenue (M USD)")
    plt.grid(axis="x", alpha=0.2)
    save_plot("top_10_revenue.png")


# Compares average revenue between franchise and standalone movies
def plot_franchise_vs_standalone(df):
    avg = df.groupby("is_franchise")["revenue_musd"].mean()
    avg.index = ["Standalone", "Franchise"]

    plt.figure(figsize=(7, 4))
    plt.bar(avg.index, avg.values, color=["orange", "mediumpurple"])

    plt.title("Franchise vs Standalone Movie Revenue")
    plt.ylabel("Average Revenue (M USD)")
    plt.grid(axis="y", alpha=0.2)
    save_plot("franchise_vs_standalone.png")


# Shows which movie genres have the highest average return on investment
def plot_roi_by_genre(df):
    roi = (
        df.assign(genre=df["genres"].str.split("|"))
        .explode("genre")
        .groupby("genre")["roi"]
        .mean()
        .sort_values()
    )

    plt.figure(figsize=(8, 5))
    roi.plot.barh(color="coral")

    plt.title("Average ROI by Movie Genre")
    plt.xlabel("Average ROI")
    plt.ylabel("Genre")
    plt.grid(axis="x", alpha=0.2)
    save_plot("roi_by_genre.png")


# Explores the relationship between movie popularity and audience ratings
def plot_popularity_vs_rating(df):
    plt.figure(figsize=(8, 5))
    plt.scatter(df["popularity"], df["vote_average"], color="darkcyan", alpha=0.5)

    plt.title("Movie Popularity vs Audience Rating")
    plt.xlabel("Popularity")
    plt.ylabel("Average Rating")
    plt.grid(alpha=0.2)
    save_plot("popularity_vs_rating.png")
