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
    assert "Best Yellow" in players_response.text
    assert ">485<" in players_response.text  # Finn's best single-day yellow (cumulative)

    days_response = client.get("/days")
    assert days_response.status_code == 200
    assert "Finn Risdon" in days_response.text


def test_days_shows_cumulative_and_sort_toggle(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days")
    assert response.status_code == 200
    assert ">485<" in response.text  # Finn's June 15 cumulative
    assert ">478<" in response.text  # Dan's June 15 cumulative
    assert 'href="/days?sort=maptap"' in response.text
    assert 'href="/days"' in response.text


def test_days_sort_by_maptap(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days?sort=maptap")
    assert response.status_code == 200
    assert "Finn Risdon" in response.text


def test_days_shows_daily_win_counts(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    cumulative_response = client.get("/days")
    assert "Daily wins (Yellow)" in cumulative_response.text
    assert "Finn Risdon · 2" in cumulative_response.text
    assert "Steve Risdon · 1" in cumulative_response.text
    assert "Daniel Chicot · 0" in cumulative_response.text

    maptap_response = client.get("/days?sort=maptap")
    assert "Daily wins (MapTap)" in maptap_response.text
    assert "Finn Risdon · 2" in maptap_response.text


def test_days_shows_green_jersey(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days")
    assert "Green jersey wins" in response.text
    assert ">Green<" in response.text  # day-table column header
    assert ">17<" in response.text  # Finn's June 15 green points
    assert ">13<" in response.text  # Dan's June 15 green points


def test_players_page_shows_green_totals(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/players")
    assert "Green Pts" in response.text
    assert ">37<" in response.text  # Finn's total green points


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
    assert "Yellow Jersey Leader" in response.text
    assert "862 total yellow" in response.text
    assert "Highest Yellow" in response.text
    assert ">485<" in response.text


def test_league_has_player_filter_chips(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/")
    assert 'data-player="all"' not in response.text
    for name in ("Daniel Chicot", "Finn Risdon", "Steve Risdon"):
        assert f'class="chip active" data-player="{name}"' in response.text


def test_players_page_has_podium(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/players")
    assert "podium" in response.text
    assert "rank-1" in response.text
    assert "rank-2" in response.text
    assert ">862</div>" in response.text  # Finn's total cumulative as the podium score
    assert "2 wins · best 485 · 5 ×100s · 2 days" in response.text


def test_days_page_has_day_cards(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days")
    assert "day-grid" in response.text
    assert "medal-1" in response.text
    assert "2026-06-20" in response.text
