# Polka Dot (King of the Mountains) Award Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Polka Dot daily award scored on rounds 3–5 (round 3 at green-jersey points, rounds 4–5 at double), with full UI parity with the green jersey.

**Architecture:** Generalize the existing green-jersey machinery in `metrics.py` (tie-splitting, day aggregation, season totals, win counts) to take a per-round points schedule; green and polka become thin wrappers over shared private functions. Thread the new `polka` fields through the existing read models, add `sort=polka` to `/days`, and mirror green in all four templates.

**Tech Stack:** Python 3 / FastAPI / Jinja2 / SQLite (stdlib `sqlite3`) / pytest. Run tests with `uv run pytest`.

**Spec:** `docs/superpowers/specs/2026-07-21-polka-dot-award-design.md`

## Global Constraints

- Rounds are 0-indexed in the DB (`rounds.idx` ∈ 0–4). Polka schedule: idx 2 → pot `(4, 2, 0)`, idx 3 → `(8, 4, 0)`, idx 4 → `(8, 4, 0)`; idx 0–1 score nothing.
- Tie-splitting identical to green: tied players split (integer-divide) the summed pot of the positions they jointly occupy.
- UI label is **"Polka"** in chips/columns, **"Polka Dot Leader"** on the hero card, **"Polka Pts"** in the players table.
- Existing public function names `green_points_by_day`, `green_jersey_totals`, `green_jersey_win_counts` must keep working unchanged (wrappers).
- Methods are named for what they return, not what they do (project convention).
- No comments that merely parrot the code. Never add Claude as co-author in commits.
- Expected sample-export polka values (fixture `tests/conftest.py::SAMPLE_EXPORT`):
  - 2026-06-15: Finn Risdon 16, Daniel Chicot 14
  - 2026-06-19: Steve Risdon 20 (solo day)
  - 2026-06-20: Finn Risdon 20 (solo day)
  - Season totals: Finn 36, Steve 20, Dan 14. Daily polka wins: Finn 2, Steve 1, Dan 0.

---

### Task 1: Generalized jersey machinery + `polka_points_by_day`

**Files:**
- Modify: `src/maptap/metrics.py:77-112` (the green points block)
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: existing `rounds`/`entries` tables via `sqlite3.Connection`.
- Produces: `polka_points_by_day(conn) -> dict[str, dict[str, int]]` (game_date ISO string → player → daily polka points). Private helpers `_round_points(scores, pot)`, `_points_by_day(conn, schedule)`, schedules `_GREEN_SCHEDULE`, `_POLKA_SCHEDULE`. `green_points_by_day` keeps its exact existing signature and behaviour.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_metrics.py` (the `_entry_with_rounds` helper at line 247 already exists; add `polka_points_by_day` to the `from maptap.metrics import (...)` block at the top):

```python
@pytest.mark.parametrize(
    ("game_date", "player", "expected"),
    [
        ("2026-06-15", "Finn Risdon", 16),   # r3: 4, r4: 8, r5: 4 (Dan 86 beats Finn 85)
        ("2026-06-15", "Daniel Chicot", 14),  # r3: 2, r4: 4, r5: 8
        ("2026-06-19", "Steve Risdon", 20),   # solo day: 4 + 8 + 8
        ("2026-06-20", "Finn Risdon", 20),    # solo day
    ],
)
def test_polka_points_by_day_over_sample_export(game_date, player, expected):
    points = polka_points_by_day(_conn())
    assert points[game_date][player] == expected


def test_polka_points_ignore_first_two_rounds():
    conn = connect()
    upsert_entries(conn, [
        _entry_with_rounds("Sprinter", 900, [100, 100, 0, 0, 0]),
        _entry_with_rounds("Climber", 800, [0, 0, 100, 100, 100]),
    ])
    points = polka_points_by_day(conn)["2026-06-15"]
    assert points == {"Climber": 20, "Sprinter": 10}


@pytest.mark.parametrize(
    ("rounds_by_player", "expected"),
    [
        # Two-way tie for first every round: (4+2)//2=3, then (8+4)//2=6 twice.
        (
            {"Alice": [90, 90, 90, 90, 90], "Bob": [90, 90, 90, 90, 90], "Carol": [80, 80, 80, 80, 80]},
            {"Alice": 15, "Bob": 15, "Carol": 0},
        ),
        # Three-way tie every round: (4+2+0)//3=2, then (8+4+0)//3=4 twice.
        (
            {"Alice": [90, 90, 90, 90, 90], "Bob": [90, 90, 90, 90, 90], "Carol": [90, 90, 90, 90, 90]},
            {"Alice": 10, "Bob": 10, "Carol": 10},
        ),
        # Tie for second every round: (2+0)//2=1, then (4+0)//2=2 twice.
        (
            {"Alice": [100, 100, 100, 100, 100], "Bob": [90, 90, 90, 90, 90], "Carol": [90, 90, 90, 90, 90]},
            {"Alice": 20, "Bob": 5, "Carol": 5},
        ),
    ],
)
def test_polka_points_split_doubled_pots_between_tied_players(rounds_by_player, expected):
    conn = connect()
    upsert_entries(conn, [
        _entry_with_rounds(player, 900, scores)
        for player, scores in rounds_by_player.items()
    ])
    assert polka_points_by_day(conn)["2026-06-15"] == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_metrics.py -v -k polka`
Expected: FAIL at import — `ImportError: cannot import name 'polka_points_by_day'`

- [ ] **Step 3: Write the implementation**

In `src/maptap/metrics.py`, replace the block from the `# Green jersey:` comment (line 77) through the end of `green_points_by_day` (line 112) with:

```python
# Per round, 1st/2nd/3rd take the pot values. Tied players split the points
# of the positions they jointly occupy (two-way tie for first with pot
# (4, 2, 0): 3 each; three-way tie: 2 each; tie for second: 1 each).
_GREEN_SCHEDULE = {idx: (4, 2, 0) for idx in range(5)}
# Polka dot (King of the Mountains): only the last three rounds score,
# and the final two are worth double.
_POLKA_SCHEDULE = {2: (4, 2, 0), 3: (8, 4, 0), 4: (8, 4, 0)}


def _round_points(scores: list[tuple[str, int]], pot: tuple[int, int, int]) -> dict[str, int]:
    ranked = sorted(scores, key=lambda ps: ps[1], reverse=True)
    points: dict[str, int] = {}
    position = 0
    while position < len(ranked):
        tied = [player for player, score in ranked if score == ranked[position][1]]
        shared = sum(pot[position:position + len(tied)])
        for player in tied:
            points[player] = shared // len(tied)
        position += len(tied)
    return points


def _points_by_day(
    conn: sqlite3.Connection, schedule: dict[int, tuple[int, int, int]]
) -> dict[str, dict[str, int]]:
    rows = conn.execute(
        """
        SELECT e.game_date, e.player, r.idx, r.score
        FROM entries e
        JOIN rounds r ON r.entry_id = e.id
        """
    ).fetchall()
    rounds: dict[tuple[str, int], list[tuple[str, int]]] = {}
    for row in rows:
        rounds.setdefault((row["game_date"], row["idx"]), []).append((row["player"], row["score"]))
    totals: dict[str, dict[str, int]] = {}
    for (game_date, idx), scores in rounds.items():
        if idx not in schedule:
            continue
        day = totals.setdefault(game_date, {})
        for player, points in _round_points(scores, schedule[idx]).items():
            day[player] = day.get(player, 0) + points
    return totals


def green_points_by_day(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    return _points_by_day(conn, _GREEN_SCHEDULE)


def polka_points_by_day(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    return _points_by_day(conn, _POLKA_SCHEDULE)
```

This deletes `_GREEN_POINTS` and `_round_green_points`; nothing else references them.

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `uv run pytest -v`
Expected: all tests PASS — the new polka tests and every pre-existing green test (the wrappers preserve behaviour exactly).

- [ ] **Step 5: Commit**

```bash
git add src/maptap/metrics.py tests/test_metrics.py
git commit -m "feat: add polka dot points via generalized jersey schedules"
```

---

### Task 2: `polka_jersey_totals` + `polka_jersey_win_counts`

**Files:**
- Modify: `src/maptap/metrics.py` (the `green_jersey_totals` and `green_jersey_win_counts` functions)
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `green_points_by_day`, `polka_points_by_day` from Task 1.
- Produces: `polka_jersey_totals(conn) -> dict[str, int]` (player → season polka total); `polka_jersey_win_counts(conn) -> list[dict]` of `{"player": str, "wins": int}` sorted by wins desc then player asc, daily rank key `(polka, cumulative, maptap_score)`. Private `_jersey_totals(by_day)`, `_jersey_win_counts(conn, points_by_day)`. Green functions keep exact signatures.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_metrics.py` (extend the metrics import block with `polka_jersey_totals, polka_jersey_win_counts`):

```python
@pytest.mark.parametrize(
    ("player", "expected"),
    [
        ("Finn Risdon", 36),
        ("Steve Risdon", 20),
        ("Daniel Chicot", 14),
    ],
)
def test_polka_jersey_totals_over_sample_export(player, expected):
    assert polka_jersey_totals(_conn())[player] == expected


@pytest.mark.parametrize(
    ("player", "expected"),
    [
        ("Finn Risdon", 2),
        ("Steve Risdon", 1),
        ("Daniel Chicot", 0),
    ],
)
def test_polka_jersey_win_counts_over_sample_export(player, expected):
    counts = {r["player"]: r["wins"] for r in polka_jersey_win_counts(_conn())}
    assert counts[player] == expected


def test_polka_jersey_win_tie_broken_by_cumulative():
    conn = connect()
    upsert_entries(conn, [
        # Both score 15 polka (3 + one round won at 8 + one lost at 4);
        # High's rounds 1-2 lift cumulative without touching polka.
        _entry_with_rounds("Polka Tied Low", 900, [90, 90, 90, 100, 90]),
        _entry_with_rounds("Polka Tied High", 880, [100, 90, 90, 90, 100]),
    ])
    counts = {r["player"]: r["wins"] for r in polka_jersey_win_counts(conn)}
    assert counts == {"Polka Tied High": 1, "Polka Tied Low": 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_metrics.py -v -k polka`
Expected: FAIL at import — `ImportError: cannot import name 'polka_jersey_totals'`

- [ ] **Step 3: Write the implementation**

In `src/maptap/metrics.py`, replace the bodies of `green_jersey_totals` (lines 115–120 pre-Task-1) and `green_jersey_win_counts` (lines 123–147) with the generalized pair plus wrappers:

```python
def _jersey_totals(by_day: dict[str, dict[str, int]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for day in by_day.values():
        for player, points in day.items():
            totals[player] = totals.get(player, 0) + points
    return totals


def green_jersey_totals(conn: sqlite3.Connection) -> dict[str, int]:
    return _jersey_totals(green_points_by_day(conn))


def polka_jersey_totals(conn: sqlite3.Connection) -> dict[str, int]:
    return _jersey_totals(polka_points_by_day(conn))


def _jersey_win_counts(
    conn: sqlite3.Connection, points_by_day: dict[str, dict[str, int]]
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT e.game_date, e.player, e.maptap_score,
               SUM(r.score) AS cumulative
        FROM entries e
        JOIN rounds r ON r.entry_id = e.id
        GROUP BY e.id
        """
    ).fetchall()
    wins: dict[str, int] = {row["player"]: 0 for row in rows}
    by_day: dict[str, list[tuple[tuple[int, int, int], str]]] = {}
    for row in rows:
        day_points = points_by_day.get(row["game_date"], {})
        rank_key = (day_points.get(row["player"], 0), row["cumulative"], row["maptap_score"])
        by_day.setdefault(row["game_date"], []).append((rank_key, row["player"]))
    for standings in by_day.values():
        best = max(rank_key for rank_key, _ in standings)
        for rank_key, player in standings:
            if rank_key == best:
                wins[player] += 1
    return [
        {"player": player, "wins": count}
        for player, count in sorted(wins.items(), key=lambda pw: (-pw[1], pw[0]))
    ]


def green_jersey_win_counts(conn: sqlite3.Connection) -> list[dict]:
    return _jersey_win_counts(conn, green_points_by_day(conn))


def polka_jersey_win_counts(conn: sqlite3.Connection) -> list[dict]:
    return _jersey_win_counts(conn, polka_points_by_day(conn))
```

Note the one intentional behaviour-preserving change inside `_jersey_win_counts`: the rank key uses `points_by_day.get(...).get(..., 0)` instead of green's original direct indexing, so schedules that skip rounds can never raise `KeyError`.

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `uv run pytest -v`
Expected: all tests PASS, including the pre-existing `test_green_jersey_totals_over_sample_export` and `test_green_jersey_win_counts_over_sample_export`.

- [ ] **Step 5: Commit**

```bash
git add src/maptap/metrics.py tests/test_metrics.py
git commit -m "feat: add polka dot season totals and daily win counts"
```

---

### Task 3: Polka in the read models and hero stats

**Files:**
- Modify: `src/maptap/metrics.py` — `all_entries`, `player_summary`, `_DAILY_SORT_KEYS`, `daily_leaderboard`, `hero_stats`
- Test: `tests/test_metrics.py` (also updates one existing test)

**Interfaces:**
- Consumes: `polka_points_by_day`, `polka_jersey_totals` from Tasks 1–2.
- Produces: each `all_entries` row and `daily_leaderboard` standing gains `"polka": int`; each `player_summary` row gains `"polka_points": int`; `hero_stats` gains `"polka_leader": str | None` and `"polka_leader_total": int | None`; `daily_leaderboard(conn, sort="polka")` orders by `(-polka, -cumulative, -maptap_score, player)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_metrics.py`:

```python
def test_all_entries_include_polka_points():
    rows = all_entries(_conn())
    dan = next(r for r in rows if r["player"] == "Daniel Chicot")
    assert dan["polka"] == 14


def test_daily_leaderboard_standings_include_polka_points():
    days = {d["game_date"]: d for d in daily_leaderboard(_conn())}
    june15 = days["2026-06-15"]
    assert june15["standings"][0]["polka"] == 16
    assert june15["standings"][1]["polka"] == 14


def test_player_summary_includes_polka_points():
    summary = {r["player"]: r for r in player_summary(_conn())}
    assert summary["Finn Risdon"]["polka_points"] == 36
    assert summary["Daniel Chicot"]["polka_points"] == 14


def test_daily_leaderboard_polka_sort_ranks_by_polka_points():
    conn = connect()
    upsert_entries(conn, [
        _entry_with_rounds("Flat Track", 800, [100, 100, 90, 90, 90]),
        _entry_with_rounds("Climber", 700, [0, 0, 100, 100, 100]),
    ])
    polka_order = [s["player"] for s in daily_leaderboard(conn, sort="polka")[0]["standings"]]
    yellow_order = [s["player"] for s in daily_leaderboard(conn)[0]["standings"]]
    assert polka_order == ["Climber", "Flat Track"]
    assert yellow_order == ["Flat Track", "Climber"]


def test_hero_stats_polka_dot_leader():
    stats = hero_stats(_conn())
    assert stats["polka_leader"] == "Finn Risdon"
    assert stats["polka_leader_total"] == 36
```

Also update the existing `test_hero_stats_empty_database` (line 428): add these two entries to the expected dict, immediately after the `"green_leader_total": None,` line:

```python
        "polka_leader": None,
        "polka_leader_total": None,
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: the five new tests FAIL (`KeyError: 'polka'` / `KeyError: 'polka_points'` / `KeyError: 'polka'` sort key / `KeyError: 'polka_leader'`), and `test_hero_stats_empty_database` FAILS on the dict mismatch. Everything else PASSES.

- [ ] **Step 3: Write the implementation**

Four edits in `src/maptap/metrics.py`:

**(a) `all_entries`** — after `green = green_points_by_day(conn)` add `polka = polka_points_by_day(conn)`, and in the appended dict after the `"green"` entry add:

```python
                "polka": polka.get(row["game_date"], {}).get(row["player"], 0),
```

**(b) `player_summary`** — after `green = green_jersey_totals(conn)` add `polka = polka_jersey_totals(conn)`, and in the returned dict after `"green_points"` add:

```python
            "polka_points": polka.get(row["player"], 0),
```

**(c) `_DAILY_SORT_KEYS` and `daily_leaderboard`** — add the sort key:

```python
_DAILY_SORT_KEYS = {
    "cumulative": lambda s: (-s["cumulative"], -s["maptap_score"], s["player"]),
    "maptap": lambda s: (-s["maptap_score"], -s["cumulative"], s["player"]),
    "green": lambda s: (-s["green"], -s["cumulative"], -s["maptap_score"], s["player"]),
    "polka": lambda s: (-s["polka"], -s["cumulative"], -s["maptap_score"], s["player"]),
}
```

In `daily_leaderboard`, after `green = green_points_by_day(conn)` add `polka = polka_points_by_day(conn)`, and in each standing dict after the `"green"` entry add:

```python
                "polka": polka.get(row["game_date"], {}).get(row["player"], 0),
```

**(d) `hero_stats`** — after the `green_leader` lines add:

```python
    polka_totals = polka_jersey_totals(conn)
    polka_leader = min(polka_totals.items(), key=lambda pt: (-pt[1], pt[0])) if polka_totals else None
```

and in the returned dict after `"green_leader_total"` add:

```python
        "polka_leader": polka_leader[0] if polka_leader else None,
        "polka_leader_total": polka_leader[1] if polka_leader else None,
```

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maptap/metrics.py tests/test_metrics.py
git commit -m "feat: expose polka dot points in read models and hero stats"
```

---

### Task 4: `/days?sort=polka` route and all four UI surfaces

**Files:**
- Modify: `src/maptap/app.py:11-18` (imports), `src/maptap/app.py:45-62` (days route)
- Modify: `src/maptap/templates/days.html`, `src/maptap/templates/index.html`, `src/maptap/templates/players.html`, `src/maptap/templates/base.html`
- Test: `tests/test_app.py` (also updates two existing tests)

**Interfaces:**
- Consumes: `polka_jersey_win_counts` (Task 2) and the `polka`/`polka_points`/`polka_leader` model fields (Task 3).
- Produces: `/days?sort=polka` renders polka-ranked standings with polka win counts; templates show the Polka column/chip/card/total.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_app.py`:

```python
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
    response = client.get("/")
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


def test_index_hero_shows_polka_dot_leader(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/")
    assert "Polka Dot Leader" in response.text
    assert "36 total polka" in response.text
```

Update two existing tests:

- `test_players_table_is_sortable` (line 200): change `assert response.text.count('data-sort="number"') == 6` to `== 7` (the new Polka Pts column).
- `test_days_shows_cumulative_and_sort_toggle` (line 53): after the `sort=green` href assertion, add `assert 'href="/days?sort=polka"' in response.text`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_app.py -v`
Expected: the five new tests FAIL (missing Polka markup); `test_players_table_is_sortable` and `test_days_shows_cumulative_and_sort_toggle` FAIL on the updated assertions. Others PASS.

- [ ] **Step 3: Write the implementation**

**(a) `src/maptap/app.py`** — add `polka_jersey_win_counts` to the metrics import block, then replace the `days` route's guard and `win_counts` expression:

```python
@app.get("/days", response_class=HTMLResponse)
def days(request: Request, sort: str = "cumulative"):
    if sort not in ("cumulative", "green", "polka"):
        sort = "cumulative"
    with closing(_conn()) as conn:
        if sort == "green":
            win_counts = green_jersey_win_counts(conn)
        elif sort == "polka":
            win_counts = polka_jersey_win_counts(conn)
        else:
            win_counts = daily_win_counts(conn, metric="cumulative")
        context = {
            "days": daily_leaderboard(conn, sort=sort),
            "win_counts": win_counts,
            "stats": hero_stats(conn),
            "active": "days",
            "sort": sort,
        }
    return templates.TemplateResponse(request, "days.html", context)
```

**(b) `src/maptap/templates/days.html`** — three edits:

After the Green chip line add:

```html
        <a class="chip {% if sort == 'polka' %}active{% endif %}" href="/days?sort=polka">Polka</a>
```

Change the wins label line to:

```html
        <span class="chip-label">Daily wins ({{ 'Green' if sort == 'green' else 'Polka' if sort == 'polka' else 'Yellow' }})</span>
```

In the day-table header row, after `<th class="num">Green</th>` add `<th class="num">Polka</th>`, and in the body row after `<td class="num">{{ s.green }}</td>` add:

```html
                    <td class="num">{{ s.polka }}</td>
```

**(c) `src/maptap/templates/index.html`** — after the Green `<th>` add:

```html
                <th class="num" rowspan="2" data-sort="number">Polka</th>
```

and after `<td class="num">{{ e.green }}</td>` add:

```html
                <td class="num">{{ e.polka }}</td>
```

**(d) `src/maptap/templates/players.html`** — after the Green Pts `<th>` add:

```html
                <th class="num" data-sort="number">Polka Pts</th>
```

and after `<td class="num">{{ p.green_points }}</td>` add:

```html
                <td class="num">{{ p.polka_points }}</td>
```

**(e) `src/maptap/templates/base.html`** — after the Green Jersey Leader `<div class="stat">…</div>` block add:

```html
                <div class="stat">
                    <div class="label">Polka Dot Leader</div>
                    <div class="value" style="font-size:22px">{{ stats.polka_leader or '—' }}</div>
                    <div class="sub">{{ stats.polka_leader_total if stats.polka_leader_total is not none else '—' }} total polka</div>
                </div>
```

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maptap/app.py src/maptap/templates tests/test_app.py
git commit -m "feat: add polka dot award to days, league, players and hero UI"
```
