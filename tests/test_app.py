import pathlib

from fastapi.testclient import TestClient

from maptap.db import connect, upsert_entries
from maptap.parser import entries_from_text
from tests.conftest import SAMPLE_EXPORT


def _build_db(path):
    conn = connect(str(path))
    upsert_entries(conn, entries_from_text(SAMPLE_EXPORT))
    conn.close()


def test_index_lists_entries(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Daniel Chicot" in response.text
    assert "955" in response.text


def test_players_and_days_routes(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    players_response = client.get("/players")
    assert players_response.status_code == 200
    assert "Finn Risdon" in players_response.text

    days_response = client.get("/days")
    assert days_response.status_code == 200
    assert "Finn Risdon" in days_response.text


def test_every_page_renders_nav_and_hero(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    for path in ("/", "/players", "/days"):
        response = client.get(path)
        assert response.status_code == 200
        assert "MAP" in response.text
        assert "TAPPERS" in response.text
        assert "/static/styles.css" in response.text
        assert "/static/theme.js" in response.text


def test_index_hero_shows_leader(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/")
    assert "Finn Risdon" in response.text
    assert "1788" in response.text
