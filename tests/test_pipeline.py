"""Simple tests: run with `python -m pytest` from the project folder. No API key or internet needed."""

import json
from unittest.mock import MagicMock

import pytest
import requests

from src import fetch_movies as fm
from src.analyze_kpis import all_kpis, roi_udf
from src.clean_movies import FINAL_COLS, add_metrics, clean_dataframe
from src.search_bruce_willis import find_bruce_willis


# a fake API answer with the given status code
def fake_response(status, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload or {}
    return r


# do not really wait between retries during tests
@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fm.time, "sleep", lambda s: None)


# write fake raw movies to a JSON Lines file and load them with Spark (like the real pipeline)
def load_raw(spark, tmp_path, movies):
    path = tmp_path / "raw.jsonl"
    path.write_text("\n".join(json.dumps(m) for m in movies))
    return spark.read.json(str(path))


# one fake raw movie in the same shape as the TMDb API answer
def raw_movie(**changes):
    movie = {
        "id": 1, "title": "Test", "tagline": "No Data", "release_date": "2020-01-01",
        "genres": [{"name": "Action"}, {"name": "Science Fiction"}],
        "belongs_to_collection": {"name": "Test Collection"},
        "original_language": "en", "budget": 100_000_000, "revenue": 0,
        "production_companies": [{"name": "A"}], "production_countries": [{"name": "US"}],
        "vote_count": 0, "vote_average": 5.0, "popularity": 1.0, "runtime": 0,
        "overview": "Story", "spoken_languages": [{"english_name": "English"}],
        "poster_path": "/p.jpg", "status": "Released", "adult": False, "video": False,
        "imdb_id": "tt1", "original_title": "Test", "homepage": "",
        "credits": {"cast": [{"name": "Bruce Willis"}],
                    "crew": [{"name": "Dir", "job": "Director"}]},
    }
    movie.update(changes)
    return movie


# --- API tests ---

def test_404_is_skipped_without_retry(monkeypatch):
    get = MagicMock(return_value=fake_response(404))
    monkeypatch.setattr(fm.requests, "get", get)
    assert fm.fetch_movie(0, "key") is None
    assert get.call_count == 1


def test_timeout_is_retried(monkeypatch):
    get = MagicMock(side_effect=[requests.exceptions.Timeout("slow"),
                                 fake_response(200, {"id": 1, "title": "X"})])
    monkeypatch.setattr(fm.requests, "get", get)
    assert fm.fetch_movie(1, "key")["title"] == "X"
    assert get.call_count == 2


def test_gives_up_after_all_retries(monkeypatch):
    get = MagicMock(return_value=fake_response(500))
    monkeypatch.setattr(fm.requests, "get", get)
    assert fm.fetch_movie(1, "key") is None
    assert get.call_count == fm.RETRIES


def test_401_stops_the_run(monkeypatch):
    get = MagicMock(return_value=fake_response(401))
    monkeypatch.setattr(fm.requests, "get", get)
    with pytest.raises(SystemExit):
        fm.fetch_movie(1, "bad-key")
    assert get.call_count == 1


# --- Cleaning tests ---

def test_cleaning_rules(spark, tmp_path):
    raw = load_raw(spark, tmp_path, [raw_movie(), raw_movie(), raw_movie(id=2, status="Rumored")])
    df = clean_dataframe(raw)

    assert df.columns == FINAL_COLS
    rows = df.collect()
    assert len(rows) == 1                          # duplicate and unreleased movie removed

    row = rows[0]
    assert row["genres"] == "Action|Science Fiction"
    assert row["belongs_to_collection"] == "Test Collection"
    assert row["budget_musd"] == 100
    assert row["revenue_musd"] is None             # 0 -> null
    assert row["runtime"] is None                  # 0 -> null
    assert row["vote_average"] is None             # 0 votes -> null
    assert row["tagline"] is None                  # placeholder -> null
    assert row["director"] == "Dir"
    assert row["cast_size"] == 1


# --- Analysis tests ---

def test_roi_udf(spark):
    df = spark.createDataFrame([(300.0, 100.0), (300.0, None)], ["revenue", "budget"])
    values = [r["roi"] for r in df.select(roi_udf("revenue", "budget").alias("roi")).collect()]
    assert values == [3.0, None]


def test_all_ten_kpis(spark, tmp_path):
    raw = load_raw(spark, tmp_path, [raw_movie(revenue=300_000_000, vote_count=50)])
    df = add_metrics(clean_dataframe(raw))
    kpis = all_kpis(df)
    assert len(kpis) == 10
    assert kpis["Highest ROI (budget >= 10M)"].first()["roi"] == 3.0


def test_search_matches_whole_names(spark, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                    # save the search CSV in a temp folder, not data/
    raw = load_raw(spark, tmp_path, [
        raw_movie(),
        raw_movie(id=2, credits={"cast": [{"name": "Bruce Willisson"}],
                                 "crew": [{"name": "Dir", "job": "Director"}]}),
    ])
    df = add_metrics(clean_dataframe(raw))
    results = find_bruce_willis(df).collect()
    assert len(results) == 1                       # "Bruce Willisson" is not a match
