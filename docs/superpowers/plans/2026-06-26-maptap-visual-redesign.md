# MapTap Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-skin the server-rendered MapTap League app with the Leeds 10K look and feel (dark/lime theme, Anton headline, panel cards, podium) without changing any data or parsing behaviour.

**Architecture:** Pure CSS + Jinja templates + two small vanilla-JS files. A new `styles.css` holds the design tokens; `base.html` gains a shared nav + hero rendered on every page; one additive metric `hero_stats(conn)` feeds the hero stat cards. No charts, no SPA, no build step.

**Tech Stack:** FastAPI, Jinja2, SQLite (stdlib sqlite3), vanilla JS, Google Fonts CDN (Anton, Hanken Grotesk, JetBrains Mono), pytest, uv.

## Global Constraints

- Accent colour is lime `#c8f135`; dark theme is default, light theme via `[data-theme='light']` toggle persisted in `localStorage`.
- Presentation-layer change only: do NOT modify `parser.py`, `db.py`, `importer.py`, the DB schema, or `Taskfile.yml`.
- No new Python dependencies; no Chart.js; no front-end build step.
- Numbers render in JetBrains Mono with `font-variant-numeric: tabular-nums`.
- No wildcard imports. Minimal/no code comments. Functions named for what they return.
- Run tests with `uv run pytest`. Hero wordmark is **MAP** (outlined) + **TAPPERS** (lime).
- Do not add Claude as a commit co-author.

---

### Task 1: `hero_stats` metric

**Files:**
- Modify: `src/maptap/metrics.py` (add `hero_stats` function at end of file)
- Test: `tests/test_metrics.py` (add tests)

**Interfaces:**
- Consumes: an open `sqlite3.Connection` (row_factory already set to `sqlite3.Row` by `maptap.db.connect`).
- Produces: `hero_stats(conn: sqlite3.Connection) -> dict` returning exactly these keys:
  - `days_tracked: int`
  - `highest_maptap: int | None`
  - `highest_maptap_player: str | None`
  - `leader: str | None`
  - `leader_total: int | None`
  - `total_hundreds: int`
  On an empty database: `days_tracked=0`, `highest_maptap=None`, `highest_maptap_player=None`, `leader=None`, `leader_total=None`, `total_hundreds=0`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_metrics.py`:

```python
def test_hero_stats_over_sample_export():
    stats = hero_stats(_conn())
    assert stats["days_tracked"] == 3
    assert stats["highest_maptap"] == 955
    assert stats["highest_maptap_player"] == "Finn Risdon"
    assert stats["leader"] == "Finn Risdon"
    assert stats["leader_total"] == 1788
    assert stats["total_hundreds"] == 6


def test_hero_stats_empty_database():
    stats = hero_stats(connect())
    assert stats == {
        "days_tracked": 0,
        "highest_maptap": None,
        "highest_maptap_player": None,
        "leader": None,
        "leader_total": None,
        "total_hundreds": 0,
    }
```

Add `hero_stats` to the existing metrics import at the top of the file:

```python
from maptap.metrics import all_entries, daily_leaderboard, hero_stats, player_summary
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_metrics.py::test_hero_stats_over_sample_export tests/test_metrics.py::test_hero_stats_empty_database -v`
Expected: FAIL with `ImportError: cannot import name 'hero_stats'`.

- [ ] **Step 3: Implement `hero_stats`**

Append to `src/maptap/metrics.py`:

```python
def hero_stats(conn: sqlite3.Connection) -> dict:
    days_tracked = conn.execute(
        "SELECT COUNT(DISTINCT game_date) AS n FROM entries"
    ).fetchone()["n"]

    highest = conn.execute(
        "SELECT player, maptap_score FROM entries "
        "ORDER BY maptap_score DESC, player ASC LIMIT 1"
    ).fetchone()

    leader = conn.execute(
        "SELECT player, SUM(maptap_score) AS total FROM entries "
        "GROUP BY player ORDER BY total DESC, player ASC LIMIT 1"
    ).fetchone()

    total_hundreds = conn.execute(
        "SELECT COUNT(*) AS n FROM rounds WHERE score = 100"
    ).fetchone()["n"]

    return {
        "days_tracked": days_tracked,
        "highest_maptap": highest["maptap_score"] if highest else None,
        "highest_maptap_player": highest["player"] if highest else None,
        "leader": leader["player"] if leader else None,
        "leader_total": leader["total"] if leader else None,
        "total_hundreds": total_hundreds,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: PASS (all metrics tests, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add src/maptap/metrics.py tests/test_metrics.py
git commit -m "feat: add hero_stats metric for redesign hero cards"
```

---

### Task 2: Theme foundation — stylesheet, theme toggle, shared nav + hero

**Files:**
- Create: `src/maptap/static/styles.css`
- Create: `src/maptap/static/theme.js`
- Modify: `src/maptap/templates/base.html` (full rewrite)
- Modify: `src/maptap/app.py` (pass `stats` + `active` to every template)
- Test: `tests/test_app.py` (add render assertions)

**Interfaces:**
- Consumes: `hero_stats(conn)` from Task 1.
- Produces: a `base.html` that defines blocks `title`, `content`, `scripts`, expects template context vars `stats` (the `hero_stats` dict) and `active` (one of `"league"`, `"players"`, `"days"`). All three routes supply both.

- [ ] **Step 1: Write the failing render tests**

Add to `tests/test_app.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_app.py -v`
Expected: FAIL — `/static/styles.css` and `1788` not in the current markup.

- [ ] **Step 3: Create `src/maptap/static/styles.css`**

```css
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Hanken+Grotesk:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {
  --bg: #0a0c0e;
  --bg-2: #11151a;
  --bg-3: #181d24;
  --panel: #12161b;
  --line: rgba(255, 255, 255, 0.09);
  --line-strong: rgba(255, 255, 255, 0.16);
  --ink: #eef2ee;
  --ink-dim: #98a2ad;
  --ink-faint: #5d6770;
  --accent: #c8f135;
  --accent-soft: rgba(200, 241, 53, 0.14);
  --accent-ink: #0a0c0e;
  --gold: #ffc94d;
  --silver: #d3dbe6;
  --bronze: #e08a4c;
  --radius: 14px;
  --radius-sm: 9px;
  --shadow: 0 24px 60px -28px rgba(0, 0, 0, 0.8);
  --maxw: 1180px;
  --mono: 'JetBrains Mono', ui-monospace, monospace;
  --display: 'Anton', sans-serif;
  --body: 'Hanken Grotesk', system-ui, sans-serif;
}

[data-theme='light'] {
  --bg: #eceae1;
  --bg-2: #ffffff;
  --bg-3: #f4f2ea;
  --panel: #ffffff;
  --line: rgba(12, 15, 18, 0.10);
  --line-strong: rgba(12, 15, 18, 0.20);
  --ink: #14181c;
  --ink-dim: #555e67;
  --ink-faint: #919aa2;
  --accent-soft: rgba(120, 150, 0, 0.16);
  --shadow: 0 24px 50px -30px rgba(20, 24, 28, 0.45);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }

body {
  font-family: var(--body);
  background: var(--bg);
  color: var(--ink);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  min-height: 100vh;
  background-image:
    radial-gradient(120% 80% at 100% -10%, rgba(200, 241, 53, 0.10), transparent 55%),
    radial-gradient(90% 70% at -10% 0%, rgba(78, 197, 255, 0.06), transparent 50%);
  background-attachment: fixed;
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  opacity: 0.5;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E");
}

.wrap { max-width: var(--maxw); margin: 0 auto; padding: 0 22px; position: relative; z-index: 1; }

/* nav */
.nav {
  position: sticky; top: 0; z-index: 50;
  backdrop-filter: blur(14px);
  background: color-mix(in srgb, var(--bg) 78%, transparent);
  border-bottom: 1px solid var(--line);
}
.nav-inner { display: flex; align-items: center; gap: 18px; height: 64px; }
.brand { display: flex; align-items: center; gap: 11px; font-weight: 800; letter-spacing: -0.02em; }
.brand .dot { width: 11px; height: 11px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 18px var(--accent); }
.brand small { display: block; font-size: 11px; color: var(--ink-dim); font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; }
.tabs { display: flex; gap: 4px; margin-left: auto; background: var(--bg-3); padding: 4px; border-radius: 999px; border: 1px solid var(--line); }
.tab {
  font: inherit; font-weight: 700; font-size: 13.5px; color: var(--ink-dim);
  text-decoration: none; padding: 8px 16px; border-radius: 999px;
  transition: color 0.18s, background 0.18s;
}
.tab:hover { color: var(--ink); }
.tab.active { background: var(--accent); color: var(--accent-ink); }
.theme-btn {
  font: inherit; cursor: pointer; width: 40px; height: 40px; border-radius: 50%;
  border: 1px solid var(--line); background: var(--bg-3); color: var(--ink);
  display: grid; place-items: center; font-size: 17px; transition: transform 0.2s, border-color 0.2s;
}
.theme-btn:hover { transform: rotate(20deg); border-color: var(--line-strong); }

/* hero */
.hero { padding: 46px 0 30px; }
.hero-tag { display: inline-flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase; color: var(--accent); }
.hero-tag::before { content: ''; width: 26px; height: 2px; background: var(--accent); }
.hero h1 {
  font-family: var(--display); font-weight: 400; line-height: 0.86; letter-spacing: 0.005em;
  font-size: clamp(48px, 10vw, 120px); margin: 14px 0 6px; text-transform: uppercase;
}
.hero h1 .em { color: var(--accent); }
.hero h1 .out { color: transparent; -webkit-text-stroke: 1.6px var(--ink); }
.hero-sub { color: var(--ink-dim); max-width: 52ch; font-size: 15px; }

.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 30px; }
.stat {
  background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--accent);
  border-radius: var(--radius); padding: 18px;
}
.stat .label { font-size: 11px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-dim); }
.stat .value { font-family: var(--mono); font-weight: 700; font-size: 30px; margin-top: 6px; }
.stat .sub { font-size: 12px; color: var(--ink-faint); margin-top: 4px; }

/* panels + section heads */
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }
.section-head { font-family: var(--display); font-weight: 400; text-transform: uppercase; font-size: 30px; letter-spacing: 0.01em; margin: 36px 0 4px; }
.section-sub { color: var(--ink-dim); font-size: 14px; margin-bottom: 16px; }
main.wrap { padding-top: 6px; padding-bottom: 60px; }

/* toolbar + chips */
.toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 14px 16px; margin: 18px 0 12px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
  font: inherit; font-weight: 600; font-size: 13px; cursor: pointer;
  color: var(--ink-dim); background: var(--bg-3); border: 1px solid var(--line);
  padding: 7px 14px; border-radius: 999px; transition: color 0.15s, background 0.15s;
}
.chip:hover { color: var(--ink); }
.chip.active { background: var(--accent); color: var(--accent-ink); border-color: transparent; }
.results-meta { margin-left: auto; color: var(--ink-faint); font-size: 13px; }

/* tables */
.table-card { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
caption { text-align: left; font-family: var(--display); text-transform: uppercase; font-size: 18px; padding: 14px 16px 0; }
th, td { padding: 11px 14px; border-bottom: 1px solid var(--line); text-align: right; white-space: nowrap; }
thead th { color: var(--ink-dim); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover { background: var(--bg-2); }
th:first-child, td:first-child, th.txt, td.txt { text-align: left; }
td.num, .num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
th[data-sort] { cursor: pointer; user-select: none; }
th[data-sort]:hover { color: var(--ink); }
.arr { font-size: 0.85em; color: var(--accent); margin-left: 2px; }
th.rounds-group { text-align: center; }
th.round, td.round { width: 2.6em; padding-left: 6px; padding-right: 6px; }
tr.hidden { display: none; }

/* podium */
.podium { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 18px 0; }
.podium-place { padding: 22px 18px; border-top: 3px solid var(--line); }
.podium-place .rank { font-family: var(--mono); font-weight: 700; font-size: 13px; }
.podium-place .who { font-size: 22px; font-weight: 800; margin: 6px 0 10px; }
.podium-place .big { font-family: var(--mono); font-weight: 700; font-size: 26px; }
.podium-place .meta { color: var(--ink-dim); font-size: 12px; margin-top: 6px; }
.rank-1 { border-top-color: var(--gold); }
.rank-1 .rank { color: var(--gold); }
.rank-2 { border-top-color: var(--silver); }
.rank-2 .rank { color: var(--silver); }
.rank-3 { border-top-color: var(--bronze); }
.rank-3 .rank { color: var(--bronze); }

/* day cards */
.day-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; margin-top: 16px; }
.medal-1 { color: var(--gold); }
.medal-2 { color: var(--silver); }
.medal-3 { color: var(--bronze); }

@media (max-width: 720px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .podium { grid-template-columns: 1fr; }
  .tabs { order: 3; width: 100%; margin: 0; justify-content: center; }
}
```

- [ ] **Step 4: Create `src/maptap/static/theme.js`**

```javascript
(function () {
  const root = document.documentElement;
  const stored = localStorage.getItem("maptap-theme") || "dark";
  root.setAttribute("data-theme", stored);

  const btn = document.getElementById("themeBtn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("maptap-theme", next);
  });
})();
```

- [ ] **Step 5: Rewrite `src/maptap/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en-GB" data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Map Tappers League{% endblock %}</title>
    <link rel="stylesheet" href="/static/styles.css">
    <script src="/static/theme.js" defer></script>
    {% block head %}{% endblock %}
</head>
<body>
    <nav class="nav">
        <div class="wrap nav-inner">
            <div class="brand">
                <span class="dot"></span>
                <span>MAP&nbsp;TAPPERS<small>maptap.gg league</small></span>
            </div>
            <div class="tabs">
                <a class="tab {{ 'active' if active == 'league' else '' }}" href="/">League</a>
                <a class="tab {{ 'active' if active == 'players' else '' }}" href="/players">Players</a>
                <a class="tab {{ 'active' if active == 'days' else '' }}" href="/days">Days</a>
            </div>
            <button class="theme-btn" id="themeBtn" title="Toggle theme" aria-label="Toggle theme">◑</button>
        </div>
    </nav>

    <header class="hero">
        <div class="wrap">
            <span class="hero-tag">maptap.gg · daily league</span>
            <h1><span class="out">Map</span> <span class="em">Tappers</span></h1>
            <p class="hero-sub">Three players, five rounds a day. Every score from the group chat, ranked and totted up.</p>
            <div class="stat-row">
                <div class="stat">
                    <div class="label">Days tracked</div>
                    <div class="value">{{ stats.days_tracked }}</div>
                    <div class="sub">in the league</div>
                </div>
                <div class="stat">
                    <div class="label">Highest MapTap</div>
                    <div class="value">{{ stats.highest_maptap if stats.highest_maptap is not none else '—' }}</div>
                    <div class="sub">{{ stats.highest_maptap_player or '—' }}</div>
                </div>
                <div class="stat">
                    <div class="label">Leader</div>
                    <div class="value" style="font-size:22px">{{ stats.leader or '—' }}</div>
                    <div class="sub">{{ stats.leader_total if stats.leader_total is not none else '—' }} total MapTap</div>
                </div>
                <div class="stat">
                    <div class="label">Total 100s</div>
                    <div class="value">{{ stats.total_hundreds }}</div>
                    <div class="sub">perfect rounds</div>
                </div>
            </div>
        </div>
    </header>

    <main class="wrap">
        {% block content %}{% endblock %}
    </main>
    {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 6: Update `src/maptap/app.py` to supply `stats` and `active`**

Replace the import line and the three route functions. The new file is:

```python
import os
import pathlib
from contextlib import closing

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from maptap.db import connect
from maptap.metrics import all_entries, daily_leaderboard, hero_stats, player_summary

_BASE = pathlib.Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

app = FastAPI(title="Map Tappers League")
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")


def _conn():
    return connect(os.environ.get("MAPTAP_DB", "maptap.db"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with closing(_conn()) as conn:
        context = {"entries": all_entries(conn), "stats": hero_stats(conn), "active": "league"}
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/players", response_class=HTMLResponse)
def players(request: Request):
    with closing(_conn()) as conn:
        context = {"players": player_summary(conn), "stats": hero_stats(conn), "active": "players"}
    return templates.TemplateResponse(request, "players.html", context)


@app.get("/days", response_class=HTMLResponse)
def days(request: Request):
    with closing(_conn()) as conn:
        context = {"days": daily_leaderboard(conn), "stats": hero_stats(conn), "active": "days"}
    return templates.TemplateResponse(request, "days.html", context)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS, including `test_every_page_renders_nav_and_hero` and `test_index_hero_shows_leader`. (Existing `test_index_lists_entries` and `test_players_and_days_routes` still pass because the data is still rendered.)

- [ ] **Step 8: Commit**

```bash
git add src/maptap/static/styles.css src/maptap/static/theme.js src/maptap/templates/base.html src/maptap/app.py tests/test_app.py
git commit -m "feat: dark/lime theme with shared nav and hero on every page"
```

---

### Task 3: League page — toolbar chips + restyled sortable table

**Files:**
- Modify: `src/maptap/templates/index.html` (full rewrite)
- Modify: `src/maptap/static/sort.js` (restyle arrow, add chip filter)
- Test: `tests/test_app.py` (add chip/filter markup assertion)

**Interfaces:**
- Consumes: `entries` context (list of dicts with `player`, `game_date`, `maptap_score`, `cumulative`, `hundreds`, `rounds`) and the `base.html` blocks from Task 2.
- Produces: a `#league` table whose `<tbody>` rows carry `data-player`, and a `.chips` toolbar of `.chip[data-player]` buttons consumed by `sort.js`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_app.py`:

```python
def test_league_has_player_filter_chips(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/")
    assert 'class="chip' in response.text
    assert 'data-player="Finn Risdon"' in response.text
    assert 'data-player="all"' in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app.py::test_league_has_player_filter_chips -v`
Expected: FAIL — chips not yet in markup.

- [ ] **Step 3: Rewrite `src/maptap/templates/index.html`**

```html
{% extends "base.html" %}
{% block title %}League · Map Tappers{% endblock %}
{% block content %}
{% set player_names = entries | map(attribute='player') | unique | sort | list %}
<h2 class="section-head">All-time league</h2>
<p class="section-sub">Every entry, sortable by any column. Filter by player below.</p>

<div class="panel toolbar">
    <div class="chips">
        <button class="chip active" data-player="all">All</button>
        {% for name in player_names %}
        <button class="chip" data-player="{{ name }}">{{ name }}</button>
        {% endfor %}
    </div>
    <span class="results-meta" id="resultsMeta">{{ entries | length }} entries</span>
</div>

<div class="panel table-card">
    <table id="league">
        <thead>
            <tr>
                <th class="txt" rowspan="2" data-sort="text">Player</th>
                <th class="txt" rowspan="2" data-sort="text">Date</th>
                <th class="num" rowspan="2" data-sort="number" data-sorted="desc">MapTap</th>
                <th class="num" rowspan="2" data-sort="number">Cumulative</th>
                <th class="num" rowspan="2" data-sort="number">#100s</th>
                <th class="rounds-group" colspan="5">Rounds</th>
            </tr>
            <tr>
                <th class="round">1</th>
                <th class="round">2</th>
                <th class="round">3</th>
                <th class="round">4</th>
                <th class="round">5</th>
            </tr>
        </thead>
        <tbody>
            {% for e in entries %}
            <tr data-player="{{ e.player }}">
                <td class="txt">{{ e.player }}</td>
                <td class="txt num">{{ e.game_date }}</td>
                <td class="num">{{ e.maptap_score }}</td>
                <td class="num">{{ e.cumulative }}</td>
                <td class="num">{{ e.hundreds }}</td>
                {% for r in e.rounds %}<td class="round num">{{ r }}</td>{% endfor %}
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
{% block scripts %}
<script src="/static/sort.js"></script>
{% endblock %}
```

- [ ] **Step 4: Rewrite `src/maptap/static/sort.js`** (arrow class becomes `arr`; add chip filter)

```javascript
(function () {
  const table = document.getElementById("league");
  if (!table) return;
  const tbody = table.tBodies[0];
  const headers = Array.from(table.querySelectorAll("th[data-sort]"));

  const arrows = new Map();
  headers.forEach((th) => {
    const arrow = document.createElement("span");
    arrow.className = "arr";
    arrow.setAttribute("aria-hidden", "true");
    th.appendChild(arrow);
    arrows.set(th, arrow);
  });

  const glyph = (descending) => (descending ? "▼" : "▲");

  const markActive = (activeTh, descending) => {
    headers.forEach((th) => {
      arrows.get(th).textContent = th === activeTh ? glyph(descending) : "";
    });
  };

  headers.forEach((th) => {
    const colIndex = Array.from(th.parentNode.children).indexOf(th);
    const sortType = th.dataset.sort;
    let descending = sortType === "number";

    const initial = th.dataset.sorted;
    if (initial) {
      const isDescending = initial === "desc";
      markActive(th, isDescending);
      descending = !isDescending;
    }

    th.addEventListener("click", () => {
      const rows = Array.from(tbody.rows);
      rows.sort((a, b) => {
        const av = a.cells[colIndex].textContent;
        const bv = b.cells[colIndex].textContent;
        if (sortType === "number") {
          return descending ? Number(bv) - Number(av) : Number(av) - Number(bv);
        }
        return descending ? bv.localeCompare(av) : av.localeCompare(bv);
      });
      rows.forEach((row) => tbody.appendChild(row));
      markActive(th, descending);
      descending = !descending;
    });
  });

  const chips = Array.from(document.querySelectorAll(".chip[data-player]"));
  const meta = document.getElementById("resultsMeta");
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const want = chip.dataset.player;
      chips.forEach((c) => c.classList.toggle("active", c === chip));
      let shown = 0;
      Array.from(tbody.rows).forEach((row) => {
        const match = want === "all" || row.dataset.player === want;
        row.classList.toggle("hidden", !match);
        if (match) shown += 1;
      });
      if (meta) meta.textContent = shown + " entries";
    });
  });
})();
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS, including `test_league_has_player_filter_chips`.

- [ ] **Step 6: Commit**

```bash
git add src/maptap/templates/index.html src/maptap/static/sort.js tests/test_app.py
git commit -m "feat: league page toolbar with player-filter chips and restyled table"
```

---

### Task 4: Players page — podium + restyled summary table

**Files:**
- Modify: `src/maptap/templates/players.html` (full rewrite)
- Test: `tests/test_app.py` (add podium assertion)

**Interfaces:**
- Consumes: `players` context (list of dicts ordered by `total_maptap` desc, each with `player`, `best`, `total_maptap`, `total_cumulative`, `total_hundreds`, `days_played`, `wins`) and `base.html` blocks.
- Produces: a `.podium` of up to three `.podium-place.rank-N` elements; no new context keys.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_app.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app.py::test_players_page_has_podium -v`
Expected: FAIL — no `podium` markup yet.

- [ ] **Step 3: Rewrite `src/maptap/templates/players.html`**

```html
{% extends "base.html" %}
{% block title %}Players · Map Tappers{% endblock %}
{% block content %}
<h2 class="section-head">Players</h2>
<p class="section-sub">Ranked by total MapTap across every day played.</p>

<div class="podium">
    {% for p in players[:3] %}
    <div class="panel podium-place rank-{{ loop.index }}">
        <div class="rank">#{{ loop.index }}</div>
        <div class="who">{{ p.player }}</div>
        <div class="big num">{{ p.total_maptap }}</div>
        <div class="meta">{{ p.wins }} wins · best {{ p.best }} · {{ p.days_played }} days</div>
    </div>
    {% endfor %}
</div>

<div class="panel table-card">
    <table>
        <thead>
            <tr>
                <th class="txt">Player</th>
                <th class="num">Best</th>
                <th class="num">Total MapTap</th>
                <th class="num">Total Cumulative</th>
                <th class="num">Total #100s</th>
                <th class="num">Days</th>
                <th class="num">Wins</th>
            </tr>
        </thead>
        <tbody>
            {% for p in players %}
            <tr>
                <td class="txt">{{ p.player }}</td>
                <td class="num">{{ p.best }}</td>
                <td class="num">{{ p.total_maptap }}</td>
                <td class="num">{{ p.total_cumulative }}</td>
                <td class="num">{{ p.total_hundreds }}</td>
                <td class="num">{{ p.days_played }}</td>
                <td class="num">{{ p.wins }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS, including `test_players_page_has_podium`.

- [ ] **Step 5: Commit**

```bash
git add src/maptap/templates/players.html tests/test_app.py
git commit -m "feat: players page podium and restyled summary table"
```

---

### Task 5: Days page — per-day standings panels

**Files:**
- Modify: `src/maptap/templates/days.html` (full rewrite)
- Test: `tests/test_app.py` (add day-card assertion)

**Interfaces:**
- Consumes: `days` context (list of dicts with `game_date` and `standings`, each standing having `position`, `player`, `maptap_score`) and `base.html` blocks.
- Produces: a `.day-grid` of `.panel` day cards with `.medal-N` ranked rows.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_app.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app.py::test_days_page_has_day_cards -v`
Expected: FAIL — no `day-grid` markup yet.

- [ ] **Step 3: Rewrite `src/maptap/templates/days.html`**

```html
{% extends "base.html" %}
{% block title %}Days · Map Tappers{% endblock %}
{% block content %}
<h2 class="section-head">By day</h2>
<p class="section-sub">Daily standings, newest first.</p>

<div class="day-grid">
    {% for day in days %}
    <div class="panel table-card">
        <table>
            <caption>{{ day.game_date }}</caption>
            <thead>
                <tr><th class="num">#</th><th class="txt">Player</th><th class="num">MapTap</th></tr>
            </thead>
            <tbody>
                {% for s in day.standings %}
                <tr>
                    <td class="num medal-{{ s.position }}">{{ s.position }}</td>
                    <td class="txt">{{ s.player }}</td>
                    <td class="num">{{ s.maptap_score }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS, including `test_days_page_has_day_cards`.

- [ ] **Step 5: Commit**

```bash
git add src/maptap/templates/days.html tests/test_app.py
git commit -m "feat: days page per-day standings panels with medal ranks"
```

---

### Task 6: Full-suite verification and browser smoke check

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `uv run pytest -v`
Expected: PASS — all tests green (the real-export test may `SKIP` if the export file is absent, which is fine).

- [ ] **Step 2: Start the app locally**

Run (background): `uv run uvicorn maptap.app:app --port 8000`
Then load http://localhost:8000/ in a browser.

- [ ] **Step 3: Visual smoke check**

Confirm by eye:
- Hero shows the giant outlined **MAP** + lime **TAPPERS** and four stat cards with real numbers.
- Nav pill highlights the current page; clicking League / Players / Days navigates and updates the highlight.
- Theme toggle (◑) flips dark↔light and the choice survives a page reload.
- League: clicking a column header sorts (lime arrow appears); clicking a player chip filters rows and the "N entries" count updates.
- Players: three podium cards coloured gold/silver/bronze; summary table below.
- Days: one card per day, rank 1/2/3 coloured gold/silver/bronze.

- [ ] **Step 4: Stop the local server**

Stop the background uvicorn process.

- [ ] **Step 5: Final confirmation**

No commit needed (all work committed per task). Report results to the user and ask whether to push (pushing triggers a Render redeploy of the live site).
```
