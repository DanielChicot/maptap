# Combative Rider Award Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Combative Rider daily award — most 100s wins, ties broken by walking down the descending-sorted round scores — shown on the days page (sort chip, 100s column, win counts), players table, and hero card.

**Architecture:** A per-day designation, not a points jersey: each entry's rank is its **combative key** (round scores sorted descending, compared lexicographically), which encodes "most 100s, then next best round" in one comparison. New metrics functions sit beside the jersey machinery in `metrics.py`; the award threads through `player_summary`, `daily_leaderboard`, and `hero_stats`, then the route and three templates.

**Tech Stack:** Python 3 / FastAPI / Jinja2 / SQLite (stdlib `sqlite3`) / pytest. Run tests with `uv run pytest`.

**Spec:** `docs/superpowers/specs/2026-07-28-combative-rider-award-design.md`

## Global Constraints

- Combative key = `tuple(sorted(scores, reverse=True))`; day winners = every player whose key equals the day's max (identical five-round sets credit both). Awarded every day, including days with no 100s.
- UI labels: "Combative" (days chip, players column), "100s" (day-table column), "Last Week's Combative" (hero card, `—`/`no rides` fallbacks).
- Win lists sort wins desc then player asc, matching the other `*_win_counts` functions. Methods are named for what they return.
- Existing behaviour of all other sorts/awards must be unchanged; whole suite passes at each task end.
- No comments that merely parrot the code. Never add Claude as co-author in commits.
- Expected sample-export values (`tests/conftest.py::SAMPLE_EXPORT`): winners — 2026-06-15 Finn Risdon, 2026-06-19 Steve Risdon (solo), 2026-06-20 Finn Risdon (solo); win counts Finn 2, Steve 1, Dan 0; June-15 hundreds: Finn 4, Dan 1. Hero with `today=2026-06-21`: combative 2 days / Finn Risdon; with `today=2026-06-19`: `None`/`None`.

---

### Task 1: Combative metrics — key, riders by day, win counts

**Files:**
- Modify: `src/maptap/metrics.py` (insert after `polka_jersey_win_counts`, before `daily_win_counts`)
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `entries`/`rounds` tables via `sqlite3.Connection`; test helpers `_conn()`, `_entry_with_rounds(player, maptap_score, scores)` already in `tests/test_metrics.py`.
- Produces: `combative_key(scores: list[int]) -> tuple[int, ...]`; `_combative_keys_by_day(conn) -> dict[str, dict[str, tuple[int, ...]]]` (game_date → player → key); `combative_riders_by_day(conn) -> dict[str, list[str]]` (winners, sorted by name); `combative_win_counts(conn) -> list[dict]` of `{"player": str, "wins": int}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_metrics.py` (extend the `from maptap.metrics import (...)` block with `combative_riders_by_day, combative_win_counts`, keeping alphabetical order):

```python
@pytest.mark.parametrize(
    ("game_date", "expected"),
    [
        ("2026-06-15", ["Finn Risdon"]),  # four 100s beat one
        ("2026-06-19", ["Steve Risdon"]),  # solo day
        ("2026-06-20", ["Finn Risdon"]),   # solo day
    ],
)
def test_combative_riders_by_day_over_sample_export(game_date, expected):
    assert combative_riders_by_day(_conn())[game_date] == expected


@pytest.mark.parametrize(
    ("rounds_by_player", "expected"),
    [
        # Tied on 100s: the next best round decides (95 beats 90).
        (
            {"Alice": [100, 100, 95, 60, 50], "Bob": [100, 100, 90, 80, 70]},
            ["Alice"],
        ),
        # Identical score sets in any order credit both players.
        (
            {"Alice": [100, 90, 80, 70, 60], "Bob": [60, 70, 80, 90, 100]},
            ["Alice", "Bob"],
        ),
        # No 100s at all: the best single round still wins the day.
        (
            {"Alice": [99, 50, 50, 50, 50], "Bob": [98, 98, 98, 98, 98]},
            ["Alice"],
        ),
    ],
)
def test_combative_riders_tie_breaks(rounds_by_player, expected):
    conn = connect()
    upsert_entries(conn, [
        _entry_with_rounds(player, 900, scores)
        for player, scores in rounds_by_player.items()
    ])
    assert combative_riders_by_day(conn)["2026-06-15"] == expected


@pytest.mark.parametrize(
    ("player", "expected"),
    [
        ("Finn Risdon", 2),
        ("Steve Risdon", 1),
        ("Daniel Chicot", 0),
    ],
)
def test_combative_win_counts_over_sample_export(player, expected):
    counts = {r["player"]: r["wins"] for r in combative_win_counts(_conn())}
    assert counts[player] == expected


def test_combative_win_counts_ordered_by_wins_then_player():
    players = [r["player"] for r in combative_win_counts(_conn())]
    assert players == ["Finn Risdon", "Steve Risdon", "Daniel Chicot"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_metrics.py -v -k combative`
Expected: FAIL at import — `ImportError: cannot import name 'combative_riders_by_day'`

- [ ] **Step 3: Write the implementation**

In `src/maptap/metrics.py`, insert after `polka_jersey_win_counts` (before `daily_win_counts`):

```python
def combative_key(scores: list[int]) -> tuple[int, ...]:
    return tuple(sorted(scores, reverse=True))


def _combative_keys_by_day(conn: sqlite3.Connection) -> dict[str, dict[str, tuple[int, ...]]]:
    rows = conn.execute(
        """
        SELECT e.game_date, e.player, r.score
        FROM entries e
        JOIN rounds r ON r.entry_id = e.id
        """
    ).fetchall()
    scores: dict[str, dict[str, list[int]]] = {}
    for row in rows:
        scores.setdefault(row["game_date"], {}).setdefault(row["player"], []).append(row["score"])
    return {
        day: {player: combative_key(rounds) for player, rounds in players.items()}
        for day, players in scores.items()
    }


def combative_riders_by_day(conn: sqlite3.Connection) -> dict[str, list[str]]:
    riders: dict[str, list[str]] = {}
    for day, keys in _combative_keys_by_day(conn).items():
        best = max(keys.values())
        riders[day] = sorted(player for player, key in keys.items() if key == best)
    return riders


def combative_win_counts(conn: sqlite3.Connection) -> list[dict]:
    players = [row["player"] for row in conn.execute("SELECT DISTINCT player FROM entries")]
    wins = {player: 0 for player in players}
    for winners in combative_riders_by_day(conn).values():
        for player in winners:
            wins[player] += 1
    return [
        {"player": player, "wins": count}
        for player, count in sorted(wins.items(), key=lambda pw: (-pw[1], pw[0]))
    ]
```

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `uv run pytest -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maptap/metrics.py tests/test_metrics.py
git commit -m "feat: add combative rider daily winners and win counts"
```

---

### Task 2: Combative in the read models and hero stats

**Files:**
- Modify: `src/maptap/metrics.py` — `player_summary`, `_DAILY_SORT_KEYS`, `daily_leaderboard`, `hero_stats`
- Test: `tests/test_metrics.py` (also updates one existing test)

**Interfaces:**
- Consumes: `_combative_keys_by_day`, `combative_riders_by_day`, `combative_win_counts` from Task 1; existing `week_start`/`last_week_start` locals in `hero_stats`.
- Produces: each `player_summary` row gains `"combative_wins": int`; each `daily_leaderboard` standing gains `"hundreds": int` and `"combative": tuple[int, ...]`; `daily_leaderboard(conn, sort="combative")` orders by the key descending then player asc; `hero_stats` gains `"last_week_combative": int | None` and `"last_week_combative_player": str | None`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_metrics.py`:

```python
def test_player_summary_includes_combative_wins():
    summary = {r["player"]: r for r in player_summary(_conn())}
    assert summary["Finn Risdon"]["combative_wins"] == 2
    assert summary["Daniel Chicot"]["combative_wins"] == 0


def test_daily_leaderboard_standings_include_hundreds():
    days = {d["game_date"]: d for d in daily_leaderboard(_conn())}
    june15 = days["2026-06-15"]
    assert june15["standings"][0]["hundreds"] == 4
    assert june15["standings"][1]["hundreds"] == 1


def test_daily_leaderboard_combative_sort_ranks_by_rounds():
    conn = connect()
    upsert_entries(conn, [
        _entry_with_rounds("Steady", 800, [90, 90, 90, 90, 90]),
        _entry_with_rounds("One Hit", 700, [100, 0, 0, 0, 0]),
    ])
    combative_order = [s["player"] for s in daily_leaderboard(conn, sort="combative")[0]["standings"]]
    yellow_order = [s["player"] for s in daily_leaderboard(conn)[0]["standings"]]
    assert combative_order == ["One Hit", "Steady"]
    assert yellow_order == ["Steady", "One Hit"]


@pytest.mark.parametrize(
    ("today", "wins", "player"),
    [
        # Sunday after the week holding all entries: Finn took 2 of the 3 awards.
        (datetime.date(2026, 6, 21), 2, "Finn Risdon"),
        # Friday inside the entries' week: the prior week is empty.
        (datetime.date(2026, 6, 19), None, None),
    ],
)
def test_hero_stats_last_week_combative(today, wins, player):
    stats = hero_stats(_conn(), today=today)
    assert stats["last_week_combative"] == wins
    assert stats["last_week_combative_player"] == player
```

Also update the existing `test_hero_stats_empty_database`: add, after the `"last_week_best_polka_player": None,` line:

```python
        "last_week_combative": None,
        "last_week_combative_player": None,
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_metrics.py -v -k "combative or hero"`
Expected: the four new tests FAIL (`KeyError`), `test_hero_stats_empty_database` FAILS on the dict mismatch; the rest PASS.

- [ ] **Step 3: Write the implementation**

Four edits in `src/maptap/metrics.py`:

**(a) `player_summary`** — after the `polka = polka_jersey_totals(conn)` line add:

```python
    combative = {row["player"]: row["wins"] for row in combative_win_counts(conn)}
```

and in the returned dict after `"polka_points"` add:

```python
            "combative_wins": combative.get(row["player"], 0),
```

**(b) `_DAILY_SORT_KEYS`** — add:

```python
    "combative": lambda s: ([-score for score in s["combative"]], s["player"]),
```

**(c) `daily_leaderboard`** — after `polka = polka_points_by_day(conn)` add `keys = _combative_keys_by_day(conn)`, and in each standing dict after the `"polka"` entry add:

```python
                "combative": keys[row["game_date"]][row["player"]],
                "hundreds": sum(1 for score in keys[row["game_date"]][row["player"]] if score == 100),
```

**(d) `hero_stats`** — after the `last_week_polka = ...` line add:

```python
    last_week_awards: dict[str, int] = {}
    for day, winners in combative_riders_by_day(conn).items():
        if last_week_start.isoformat() <= day < week_start.isoformat():
            for player in winners:
                last_week_awards[player] = last_week_awards.get(player, 0) + 1
    last_week_combative = (
        min(last_week_awards.items(), key=lambda pw: (-pw[1], pw[0])) if last_week_awards else None
    )
```

and in the returned dict after `"last_week_best_polka_player"` add:

```python
        "last_week_combative": last_week_combative[1] if last_week_combative else None,
        "last_week_combative_player": last_week_combative[0] if last_week_combative else None,
```

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maptap/metrics.py tests/test_metrics.py
git commit -m "feat: expose combative rider in read models and hero stats"
```

---

### Task 3: `/days?sort=combative` route and the three UI surfaces

**Files:**
- Modify: `src/maptap/app.py` (metrics import block; `days` route)
- Modify: `src/maptap/templates/days.html`, `src/maptap/templates/players.html`, `src/maptap/templates/base.html`
- Test: `tests/test_app.py` (also updates three existing tests)

**Interfaces:**
- Consumes: `combative_win_counts` (Task 1); `combative_wins` / `hundreds` / `last_week_combative*` model fields (Task 2).
- Produces: `/days?sort=combative` renders combative-ranked standings with combative win counts; templates show the chip, 100s column, players column, and hero card.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_app.py`:

```python
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


def test_days_shows_hundreds_column(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/days")
    assert ">100s<" in response.text
    assert 'href="/days?sort=combative"' in response.text
    assert ">4<" in response.text  # Finn's June 15 hundreds


def test_players_page_shows_combative_wins(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/players")
    assert ">Combative</th>" in response.text
```

Update three existing tests:

- `test_days_shows_cumulative_and_sort_toggle`: after the polka href assertion add `assert 'href="/days?sort=combative"' in response.text`.
- `test_players_table_is_sortable`: change `assert response.text.count('data-sort="number"') == 7` to `== 8`.
- `test_index_hero_shows_stat_cards`: after the `"Last Week's Best Polka"` assertion add `assert "Last Week's Combative" in response.text`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_app.py -v`
Expected: the three new tests FAIL (missing markup); the three updated assertions FAIL; others PASS.

- [ ] **Step 3: Write the implementation**

**(a) `src/maptap/app.py`** — add `combative_win_counts` to the metrics import block, alphabetically (between `all_entries` and `daily_leaderboard`). Replace the `days` route guard and win-counts selection:

```python
    if sort not in ("cumulative", "green", "polka", "combative"):
        sort = "cumulative"
    with closing(_conn()) as conn:
        if sort == "green":
            win_counts = green_jersey_win_counts(conn)
        elif sort == "polka":
            win_counts = polka_jersey_win_counts(conn)
        elif sort == "combative":
            win_counts = combative_win_counts(conn)
        else:
            win_counts = daily_win_counts(conn, metric="cumulative")
```

**(b) `src/maptap/templates/days.html`** — three edits:

After the Polka chip line add:

```html
        <a class="chip {% if sort == 'combative' %}active{% endif %}" href="/days?sort=combative">Combative</a>
```

Replace the wins label line with the dict lookup (four sorts now):

```html
        <span class="chip-label">Daily wins ({{ {'green': 'Green', 'polka': 'Polka', 'combative': 'Combative'}.get(sort, 'Yellow') }})</span>
```

In the day-table header row, after `<th class="num">Polka</th>` add `<th class="num">100s</th>`, and in the body row after `<td class="num">{{ s.polka }}</td>` add:

```html
                    <td class="num">{{ s.hundreds }}</td>
```

**(c) `src/maptap/templates/players.html`** — after the Polka Pts `<th>` add:

```html
                <th class="num" data-sort="number">Combative</th>
```

and after `<td class="num">{{ p.polka_points }}</td>` add:

```html
                <td class="num">{{ p.combative_wins }}</td>
```

**(d) `src/maptap/templates/base.html`** — after the Last Week's Best Polka `<div class="stat">…</div>` block add:

```html
                <div class="stat">
                    <div class="label">Last Week's Combative</div>
                    <div class="value">{{ stats.last_week_combative if stats.last_week_combative is not none else '—' }}</div>
                    <div class="sub">{{ stats.last_week_combative_player or 'no rides' }}</div>
                </div>
```

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maptap/app.py src/maptap/templates tests/test_app.py
git commit -m "feat: add combative rider to days, players and hero UI"
```
