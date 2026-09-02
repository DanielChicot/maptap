import pathlib
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from maptap.db import connect, upsert_entries
from maptap.parser import entries_from_text
from tests.conftest import SAMPLE_EXPORT


def _build_db(path):
    conn = connect(str(path))
    upsert_entries(conn, entries_from_text(SAMPLE_EXPORT))
    conn.close()


class _StartTagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.collected = []

    def handle_starttag(self, tag, attrs):
        self.collected.append((tag, attrs))


def _start_tags(markup):
    """Start tags a browser would actually build from this markup, as (tag, attrs)."""
    collector = _StartTagCollector()
    collector.feed(markup)
    return collector.collected


def test_index_lists_entries(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/league")
    assert response.status_code == 200
    assert "Daniel Chicot" in response.text
    assert ">485<" in response.text  # Finn's June 15 yellow tops the table
    assert ">Green<" in response.text
    assert ">17<" in response.text  # Finn's June 15 green points
    assert ">MapTap<" not in response.text


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
    assert "MapTap" not in players_response.text

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
    assert 'href="/days?sort=green"' in response.text
    assert 'href="/days"' in response.text
    assert 'href="/days?sort=maptap"' not in response.text
    assert 'href="/days?sort=polka"' in response.text
    assert 'href="/days?sort=combative"' in response.text


def test_days_sort_by_green(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days?sort=green")
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

    green_response = client.get("/days?sort=green")
    assert "Daily wins (Green)" in green_response.text
    assert "Finn Risdon · 2" in green_response.text
    assert "Steve Risdon · 1" in green_response.text


def test_days_shows_green_jersey(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days")
    assert ">Green<" in response.text  # day-table column header
    assert ">17<" in response.text  # Finn's June 15 green points
    assert ">13<" in response.text  # Dan's June 15 green points
    assert ">MapTap<" not in response.text  # MapTap gone from tables and toggle


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
    for path in ("/league", "/players", "/days"):
        response = client.get(path)
        assert response.status_code == 200
        assert "MAP" in response.text
        assert "TAPPERS" in response.text
        assert "/static/styles.css" in response.text
        assert "/static/theme.js" in response.text


def test_index_hero_shows_stat_cards(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/")
    assert "Highest Yellow" in response.text
    assert ">485<" in response.text
    assert "This Week's Best" in response.text
    assert "Last Week's Best" in response.text
    assert "Last Week's Best Green" in response.text
    assert "Last Week's Best Polka" in response.text
    assert "Last Week's Combative" in response.text
    assert "Yellow Jersey Leader" not in response.text
    assert "Green Jersey Leader" not in response.text
    assert "Polka Dot Leader" not in response.text
    assert "Highest MapTap" not in response.text
    assert "MapTap Leader" not in response.text


def test_league_has_player_filter_chips(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/league")
    assert 'data-player="all"' not in response.text
    for name in ("Daniel Chicot", "Finn Risdon", "Steve Risdon"):
        assert f'class="chip active" data-player="{name}"' in response.text


def test_players_table_is_sortable(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/players")
    assert "data-sortable" in response.text
    assert "/static/sort.js" in response.text
    assert 'data-sort="text"' in response.text
    assert response.text.count('data-sort="number"') == 7
    assert 'data-sorted="desc"' in response.text  # Total Yellow carries the default order


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


def test_days_sort_by_polka(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days?sort=polka")
    assert response.status_code == 200
    assert "Daily wins (Polka)" in response.text
    assert "Finn Risdon · 2" in response.text
    assert "Steve Risdon · 1" in response.text


def test_days_shows_polka_column(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days")
    assert ">Polka<" in response.text
    assert 'href="/days?sort=polka"' in response.text
    assert ">16<" in response.text  # Finn's June 15 polka points
    assert ">14<" in response.text  # Dan's June 15 polka points


def test_index_shows_polka_column(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/league")
    assert ">Polka<" in response.text
    assert ">16<" in response.text  # Finn's June 15 polka points


def test_players_page_shows_polka_totals(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/players")
    assert "Polka Pts" in response.text
    assert ">36<" in response.text  # Finn's total polka points


def test_root_redirects_to_days(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    redirect = client.get("/", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "/days"
    response = client.get("/")
    assert "By day" in response.text


def test_nav_lists_days_first(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days")
    assert 'href="/league">League</a>' in response.text
    assert response.text.index(">Days</a>") < response.text.index(">League</a>")
    assert response.text.index(">League</a>") < response.text.index(">Players</a>")


def test_days_unknown_sort_falls_back_to_cumulative(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days?sort=bogus")
    assert response.status_code == 200
    assert "Daily wins (Yellow)" in response.text


def test_days_sort_by_combative(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days?sort=combative")
    assert response.status_code == 200
    assert "Daily wins (Combative)" in response.text
    assert "Finn Risdon · 2" in response.text
    assert "Steve Risdon · 1" in response.text


def test_days_shows_combative_points_column(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days")
    assert response.text.count(">Combative</th>") == 3  # one per sample day card
    assert ">100s<" not in response.text
    assert "✓" not in response.text
    assert 'href="/days?sort=combative"' in response.text
    assert ">4<" in response.text  # Finn's June 15 combative points


def test_players_page_shows_combative_points(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/players")
    assert ">Combative</th>" in response.text
    assert ">5<" in response.text  # Finn's season combative points
    assert "Total #100s" not in response.text


@pytest.mark.parametrize("route", ["/league", "/players", "/days"])
def test_tables_parse_with_a_real_thead(route, tmp_path, monkeypatch):
    """sort.js reads table.tBodies[0]; an unclosed <table> tag puts headers there instead."""
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    tags = _start_tags(client.get(route).text)

    tables = [attrs for tag, attrs in tags if tag == "table"]
    assert tables, f"{route} renders no table"
    swallowed = [name for attrs in tables for name, _ in attrs if name.startswith("<")]
    assert not swallowed, f"{route} has an unclosed <table> tag, swallowing {swallowed}"
    assert any(tag == "thead" for tag, _ in tags), f"{route} renders no <thead> element"


def test_days_renders_a_hidden_rounds_row_per_standing(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    response = TestClient(app).get("/days")
    tags = _start_tags(response.text)

    rounds_rows = [dict(a) for t, a in tags if t == "tr" and "rounds-row" in (dict(a).get("class") or "")]
    assert len(rounds_rows) == 4  # one per entry in SAMPLE_EXPORT
    assert all("hidden" in row for row in rounds_rows)

    toggles = [dict(a) for t, a in tags if t == "tr" and dict(a).get("aria-expanded") is not None]
    assert len(toggles) == 4
    assert all(t["aria-expanded"] == "false" and t["role"] == "button" and t["tabindex"] == "0" for t in toggles)

    spans = [dict(a) for t, a in tags if t == "td" and dict(a).get("colspan") == "6"]
    assert len(spans) == 4

    assert "R1 4 🤮" in response.text  # Finn's June 20 opener, score and emoji together
    assert "/static/expand.js" in response.text
