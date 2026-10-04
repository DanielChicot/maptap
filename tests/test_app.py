import pathlib
import re
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


def test_days_shows_cumulative_without_rank_toggle(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days")
    assert response.status_code == 200
    assert ">485<" in response.text  # Finn's June 15 cumulative
    assert ">478<" in response.text  # Dan's June 15 cumulative
    assert "Rank by" not in response.text
    assert "/days?sort=" not in response.text


def _win_row(markup, competition):
    """The markup of one competition's win-count row on the days page."""
    return markup.split(f'id="wins-{competition}"', 1)[1].split("</div>", 1)[0]


def _days_markup(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    return TestClient(app).get("/days").text


def test_days_win_switcher_has_a_button_per_competition_with_yellow_selected(tmp_path, monkeypatch):
    buttons = [
        (attrs["aria-controls"], attrs["aria-pressed"])
        for tag, attrs in map(lambda t: (t[0], dict(t[1])), _start_tags(_days_markup(tmp_path, monkeypatch)))
        if tag == "button" and "aria-controls" in attrs
    ]
    assert buttons == [("wins-yellow", "true"), ("wins-green", "false"), ("wins-combative", "false")]


@pytest.mark.parametrize(
    ("competition", "hidden"),
    [("yellow", False), ("green", True), ("combative", True)],
)
def test_days_shows_only_the_yellow_win_row_initially(competition, hidden, tmp_path, monkeypatch):
    rows = {
        attrs["id"]: attrs
        for tag, attrs in map(lambda t: (t[0], dict(t[1])), _start_tags(_days_markup(tmp_path, monkeypatch)))
        if tag == "div" and attrs.get("id", "").startswith("wins-")
    }
    assert ("hidden" in rows[f"wins-{competition}"]) is hidden


def test_days_loads_win_switcher_script(tmp_path, monkeypatch):
    assert "/static/wins.js" in _days_markup(tmp_path, monkeypatch)


@pytest.mark.parametrize(
    ("competition", "chip"),
    [
        ("yellow", "Finn Risdon · 2"),
        ("yellow", "Steve Risdon · 1"),
        ("yellow", "Daniel Chicot · 0"),
        ("green", "Finn Risdon · 2"),
        ("green", "Steve Risdon · 1"),
        ("combative", "Finn Risdon · 2"),
        ("combative", "Steve Risdon · 1"),
    ],
)
def test_days_win_rows_show_counts(competition, chip, tmp_path, monkeypatch):
    assert chip in _win_row(_days_markup(tmp_path, monkeypatch), competition)


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
    assert "Last Week's Best Polka" not in response.text
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
    assert response.text.count('data-sort="number"') == 10
    assert 'data-sort="number" data-sorted="desc">Avg Yellow<' in response.text  # mean yellow carries the default order



def test_day_tables_are_sortable(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days")
    days = response.text.count("<caption>")
    assert response.text.count("<table data-sortable>") == days
    assert "/static/sort.js" in response.text
    assert response.text.count('data-sort="text"') == days
    assert response.text.count('data-sort="number"') == 4 * days
    assert response.text.count('data-sorted="desc">Yellow<') == days  # yellow ranking carries the default order


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


@pytest.mark.parametrize("sort", ["green", "combative", "polka", "bogus"])
def test_old_sort_links_rank_by_yellow(sort, tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    response = TestClient(app).get(f"/days?sort={sort}")
    assert response.status_code == 200
    days = response.text.count("<caption>")
    assert response.text.count('data-sorted="desc">Yellow<') == days


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
    assert ">4<" in response.text  # Finn's June 15 combative points



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

    spans = [dict(a) for t, a in tags if t == "td" and dict(a).get("colspan") == "5"]
    assert len(spans) == 4

    visible_text = re.sub(r"<[^>]+>", "", response.text)
    assert "4 🤮 · 100 🎯 · 90 👑 · 94 🏅 · 89 👑" in visible_text  # Finn's June 20, no round labels
    assert "/static/expand.js" in response.text


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, "Zero"), (1, "One"), (3, "Three"), (5, "Five"), (12, "Twelve"), (13, "13"), (40, "40"),
    ],
)
def test_number_word_spells_small_counts(count, expected):
    from maptap.app import number_word

    assert number_word(count) == expected


def test_hero_subtitle_counts_the_players(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    response = TestClient(app).get("/days")
    assert "Three players, five rounds a day." in response.text
    assert "Three player," not in response.text  # plural agrees with the count


def _players_table(markup):
    """Header labels and per-player cell texts of the players table, in rendered order."""
    table = markup.split("<table data-sortable>", 1)[1].split("</table>", 1)[0]
    head, body = table.split("<tbody>", 1)
    cells = lambda html, tag: [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.S)]
    rows = [cells(r, "td") for r in re.findall(r"<tr>(.*?)</tr>", body, re.S)]
    return cells(head, "th"), {row[0]: row[1:] for row in rows}, [row[0] for row in rows]


def test_players_page_columns_are_bests_averages_wins_and_days(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    headers, _, order = _players_table(TestClient(app).get("/players").text)
    assert headers == [
        "Player",
        "Best Yellow", "Best Green", "Best Combative",
        "Avg Yellow", "Avg Green", "Avg Combative",
        "Yellow Wins", "Green Wins", "Combative Wins", "Days",
    ]
    assert order == ["Daniel Chicot", "Finn Risdon", "Steve Risdon"]  # by mean yellow


@pytest.mark.parametrize(
    ("player", "expected"),
    [
        # Finn's best green comes from June 20, his best combative from June 15.
        ("Finn Risdon", ["485", "20", "4", "431.0", "18.5", "2.5", "2", "2", "2", "2"]),
        ("Daniel Chicot", ["478", "13", "1", "478.0", "13.0", "1.0", "0", "0", "0", "1"]),
        ("Steve Risdon", ["413", "20", "0", "413.0", "20.0", "0.0", "1", "1", "1", "1"]),
    ],
)
def test_players_page_row(player, expected, tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    _, rows, _ = _players_table(TestClient(app).get("/players").text)
    assert rows[player] == expected


@pytest.mark.parametrize("route", ["/days", "/league", "/players"])
def test_no_page_mentions_polka(route, tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    assert "polka" not in TestClient(app).get(route).text.lower()
