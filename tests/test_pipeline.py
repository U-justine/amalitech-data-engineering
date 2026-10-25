"""Unit tests: run with `python -m pytest` from the project root."""

from unittest.mock import MagicMock

import pandas as pd
import pytest
import requests

from src import fetch_movies as fm
from src.analyze_kpis import all_kpis
from src.clean_movies import FINAL_COLUMNS, add_derived_metrics, clean_dataframe
from src.search_movies import search_movies
from src.validate_clean_data import validate_clean_data


def _response(status, payload=None):
    r = MagicMock()
    r.status_code = status
    r.reason = "reason"
    r.json.return_value = payload or {}
    return r


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fm.time, "sleep", lambda s: None)


def test_404_is_skipped_without_retry():
    session = MagicMock()
    session.get.return_value = _response(404)
    movie, failure = fm.fetch_movie(0, "key", session)
    assert movie is None and failure["status"] == 404
    assert session.get.call_count == 1


def test_retries_then_succeeds_on_5xx():
    session = MagicMock()
    session.get.side_effect = [_response(503), _response(200, {"id": 1, "title": "X"})]
    movie, failure = fm.fetch_movie(1, "key", session)
    assert movie["title"] == "X" and failure is None
    assert session.get.call_count == 2


def test_timeout_gives_up_after_max_retries():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.Timeout("slow")
    movie, failure = fm.fetch_movie(1, "key", session)
    assert movie is None and "Timeout" in failure["reason"]
    assert session.get.call_count == fm.MAX_RETRIES


def test_401_is_not_retried():
    session = MagicMock()
    session.get.return_value = _response(401)
    _, failure = fm.fetch_movie(1, "bad-key", session)
    assert failure["status"] == 401 and session.get.call_count == 1


def _raw_movie(**overrides):
    movie = {
        "id": 1, "title": "Test", "tagline": "No Data", "release_date": "2020-01-01",
        "genres": [{"name": "Action"}, {"name": "Science Fiction"}],
        "belongs_to_collection": {"name": "Test Collection"},
        "original_language": "en", "budget": 100_000_000, "revenue": 0,
        "production_companies": [{"name": "A"}], "production_countries": [{"name": "US"}],
        "vote_count": 0, "vote_average": 5.0, "popularity": 1.0, "runtime": 0,
        "overview": "Story", "spoken_languages": [{"english_name": "English"}],
        "poster_path": "/p.jpg", "status": "Released", "adult": False, "video": False,
        "imdb_id": "tt1", "original_title": "Test", "homepage": "", "softcore": False,
        "origin_country": ["US"],
        "credits": {"cast": [{"name": "Bruce Willis", "order": 0}],
                    "crew": [{"name": "Dir", "job": "Director"}]},
    }
    movie.update(overrides)
    return movie


def test_cleaning_rules():
    raw = [_raw_movie(), _raw_movie(), _raw_movie(id=2, status="Rumored")]
    df = clean_dataframe(raw)
    assert list(df.columns) == FINAL_COLUMNS
    assert len(df) == 1                      # duplicate + unreleased removed
    row = df.iloc[0]
    assert row["genres"] == "Action|Science Fiction"
    assert row["belongs_to_collection"] == "Test Collection"
    assert row["budget_musd"] == 100
    assert pd.isna(row["revenue_musd"]) and pd.isna(row["runtime"])   # zeros -> NaN
    assert pd.isna(row["vote_average"])      # vote_count = 0
    assert pd.isna(row["tagline"])           # placeholder
    assert validate_clean_data(df)


def test_search_matches_whole_names_and_genres():
    df = clean_dataframe([_raw_movie()])
    assert len(search_movies(df, genres=["Science Fiction", "Action"], actor="Bruce Willis")) == 1
    assert len(search_movies(df, genres=["Drama"], actor="Bruce Willis")) == 0
    assert len(search_movies(df, actor="Bruce")) == 0


def test_all_ten_kpis():
    df = add_derived_metrics(clean_dataframe([_raw_movie(revenue=300_000_000, vote_count=50)]))
    assert len(all_kpis(df)) == 10
