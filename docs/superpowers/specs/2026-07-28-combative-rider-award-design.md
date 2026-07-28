# Combative Rider Daily Award — Design

**Date:** 2026-07-28
**Status:** Approved (design); pending spec review

## Purpose

Add a third daily award alongside the green and polka dot jerseys: the
**Combative Rider**, awarded each day to whoever scores the most 100s, with
ties broken by the next best round score. Unlike the jerseys it carries no
points value — it is a per-day designation, and what accumulates is the
count of days won.

## Award rules

Each player's entry for a day is ranked by its **combative key**: the five
round scores sorted descending, compared lexicographically.

- More 100s at the front of the key automatically outranks fewer.
- Tied on 100s, the comparison walks down to the next best round, then the
  next, and so on — `(100, 100, 95, …)` beats `(100, 100, 90, …)`.
- The award is granted every day, Tour-style: on a day with no 100s the
  same comparison still crowns the best round(s).
- Players with **identical** five-round sets are both credited (the same
  convention as daily win counts and jersey win counts).

Season standing = number of days won.

## Components

### `metrics.py`

- `combative_key(scores: list[int]) -> tuple[int, ...]` — the round scores
  sorted descending. Named for what it returns, per project convention.
- `combative_riders_by_day(conn) -> dict[str, list[str]]` — game_date ISO
  string → winners (usually one, more on identical-rounds ties).
- `combative_win_counts(conn) -> list[dict]` — `{"player": str, "wins":
  int}`, sorted wins desc then player asc, mirroring
  `green_jersey_win_counts` / `daily_win_counts`.
- `player_summary` rows gain `"combative_wins": int`.
- `daily_leaderboard`:
  - each standing gains `"hundreds": int` (count of 100-rounds that day)
    and `"combative": tuple[int, ...]` (the key, used for sorting);
  - `_DAILY_SORT_KEYS` gains `"combative"`, ordering by the key descending
    then player asc:
    `lambda s: ([-r for r in s["combative"]], s["player"])`.
- `hero_stats` gains `"last_week_combative": int | None` and
  `"last_week_combative_player": str | None` — the player who won the
  award on the most days last week (Sunday–Saturday, same week logic as
  the other last-week cards); value is that number of days; ties break
  alphabetically. `None`/`None` when last week has no entries.

### `app.py`

`/days` accepts `sort=combative` (alongside `cumulative`, `green`,
`polka`); the daily-wins panel uses `combative_win_counts` for that sort.

### Templates

- `days.html` — "Combative" rank-by chip (`/days?sort=combative`); a
  "100s" column in each day table after Polka; the daily-wins chip label
  becomes a dict lookup now that there are four sorts:
  `{{ {'green': 'Green', 'polka': 'Polka', 'combative': 'Combative'}.get(sort, 'Yellow') }}`.
- `players.html` — sortable "Combative" numeric column (career days won)
  after "Polka Pts".
- `base.html` — hero card "Last Week's Combative": the days-won count as
  the value, the player underneath, `—`/`no rides` fallbacks matching the
  green/polka cards.
- `index.html` (league table) — unchanged: it already shows #100s per
  entry.

## Expected sample-export values

- 2026-06-15: Finn `(100,100,100,100,85)` beats Dan `(100,99,98,95,86)` →
  Finn.
- 2026-06-19: Steve (solo) → Steve. 2026-06-20: Finn (solo) → Finn.
- Win counts: Finn 2, Steve 1, Dan 0.
- Hero with `today=2026-06-21` (Sunday after all entries): combative =
  2 days, Finn Risdon. With `today=2026-06-19`: prior week empty →
  `None`/`None`.

## Testing

Pytest, parameterized where natural:

1. `combative_riders_by_day`: most-100s wins; walk-down tie-break; two
   identical five-round sets credit both; a 100-less day still awards.
2. `combative_win_counts` over the sample export, plus ordering.
3. `daily_leaderboard(sort="combative")` ordering and the new `hundreds`
   field.
4. `/days?sort=combative` route (chip active, "Daily wins (Combative)"),
   players column, hero card — mirroring the polka app tests.
5. `hero_stats` last-week combative fields, parameterized over the two
   `today` cases; empty-database dict gains the two `None` keys (existing
   test updated — plan-mandated).

## Out of scope

- No changes to jersey scoring, the import pipeline, or the league table.
- Derived on read: historical days get combative riders automatically.
