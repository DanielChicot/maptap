# Map Tappers League — Design

**Date:** 2026-06-22
**Status:** Approved (design); pending spec review

## Purpose

Surface league-table style statistics from the daily [maptap.gg](https://www.maptap.gg)
scores that three players (Daniel Chicot, Steve Risdon, Finn Risdon) post to the
"Map Tappers" WhatsApp group. The source is an exported WhatsApp chat `.txt` file.

The centrepiece is a sortable all-time table of every score entry, rankable by the
maptap weighted "Final score", by the simple sum of the five round scores, and by
the number of 100s in that entry — plus per-player and per-day views.

## Source data shape

Each scoring message looks like:

```
15/06/2026, 07:37 - Daniel Chicot: www.maptap.gg June 15
100🎯 99🎯 98🎯 95🏅 86🌟
Final score: 938
```

- One message = one player's entry for one day.
- Exactly five round scores, each with a trailing emoji (decorative; not the score).
- `Final score` is maptap's **weighted/bonus** score and is **not** the sum of the
  five rounds (100+99+98+95+86 = 478, yet Final score = 938). These are two
  distinct metrics.
- The "June 15" label has no year; the year is taken from the message timestamp.
- Non-scoring messages (chatter, `<Media omitted>`, links) are ignored.

## Stack

- Python + FastAPI (server), Jinja2 (templating), SQLite (stdlib `sqlite3`).
- Frontend: server-rendered table + ~30 lines of vanilla JS for instant
  client-side column sorting. No SPA framework. Dataset is tiny (~3 players × days).
- Tests: `pytest`, parameterized where natural.

## Architecture

```mermaid
flowchart LR
    txt["WhatsApp .txt export"] --> parser["parser.py (pure)"]
    parser --> entries["Entry records"]
    entries --> db["db.py upsert"]
    db --> sqlite[("SQLite")]
    sqlite --> metrics["metrics.py (queries)"]
    metrics --> app["app.py (FastAPI + Jinja2)"]
    app --> browser["Browser (vanilla-JS column sort)"]
```

### Components

Each unit has one purpose, a clear interface, and is independently testable.

1. **`parser.py`** — pure function `entries_from_text(text: str) -> list[Entry]`.
   No I/O, no DB. `Entry` is an immutable dataclass:
   `player: str`, `game_date: date`, `maptap_score: int`,
   `rounds: tuple[Round, ...]` where `Round` is `(score: int, emoji: str)`.
   Skips non-score messages; logs a warning for any `maptap.gg` message it cannot
   parse so malformed posts surface rather than silently vanish.

2. **`db.py`** — schema creation + idempotent upsert.
   - `entries(id INTEGER PK, player TEXT, game_date TEXT, maptap_score INTEGER,
     UNIQUE(player, game_date))`
   - `rounds(entry_id INTEGER, idx INTEGER, score INTEGER, emoji TEXT,
     PRIMARY KEY(entry_id, idx))`
   - Upsert keyed on `(player, game_date)`: re-importing updates an existing day,
     inserts new ones, never duplicates. `rounds` for an entry are replaced on
     upsert.

3. **`importer.py`** — glue: read file → `parser` → `db` upsert. Re-runnable: drop
   a fresh export in and re-run. CLI entry point, e.g.
   `python -m maptap.importer "WhatsApp Chat with Map Tappers.txt"`.

4. **`metrics.py`** — pure query functions returning derived views:
   - `all_entries()` → rows of
     `(player, game_date, maptap_score, cumulative, hundreds, rounds)` where
     `cumulative = SUM(rounds.score)` and `hundreds = COUNT(rounds.score = 100)`.
   - `player_summary()` → per player: personal best (max maptap), total maptap,
     total cumulative, total 100s, days played, daily wins.
   - `daily_leaderboard()` → per game_date: players ranked by maptap_score with
     positions.

5. **`app.py`** — FastAPI app. Routes:
   - `GET /` — main page: the sortable all-entries league table (default sort:
     maptap_score desc) with a **scoring-mode toggle** (MapTap weighted ↔
     Sum-of-efforts) that re-sorts/re-ranks client-side.
   - `GET /players` — per-player summary view.
   - `GET /days` — per-day leaderboard view.

## Views

### 1. All-entries sortable table (primary)
Columns: Player · Date · MapTap score · Cumulative (Σ rounds) · #100s · the five
rounds. Any header click sorts instantly (vanilla JS). Scoring-mode toggle switches
the ranking emphasis between weighted and sum-of-efforts.

### 2. Per-player summary
Personal best, total maptap, total cumulative, total 100s, days played, daily wins.

### 3. Per-day leaderboard
For each date, players ranked 1st/2nd/3rd by maptap score.

## Error handling

- Parser ignores non-scoring messages silently.
- Parser logs a warning (does not crash) for `maptap.gg` messages that don't match
  the expected shape, so malformed entries are visible.
- Importer is idempotent; safe to re-run on overlapping exports.

## Testing

- **Parser:** parameterized tests over the real export plus crafted edge cases
  (missing emoji, extra whitespace, the worst-day message with leading chatter).
- **Metrics:** assert known facts derived from the source data —
  - top entry by maptap = Daniel 987 (June 22);
  - Finn has two entries with four 100s (June 15, June 18);
  - sum-of-efforts ranking places Steve's June 15 (471) in the top 10;
  - personal bests: Daniel 987, Finn 973, Steve 939.
- **Importer:** importing the same export twice yields identical row counts
  (idempotency).

## Out of scope (YAGNI)

- Authentication, hosting/deployment, multi-group support.
- Automated WhatsApp ingestion (export is manual).
- Charts/graphs (tables only for now).

## Notes

- The working directory is not currently a git repository. The design doc is
  written to disk; initialising git / committing is deferred to the user's
  preference.
