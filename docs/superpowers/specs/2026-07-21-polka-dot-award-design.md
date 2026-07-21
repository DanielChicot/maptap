# Polka Dot (King of the Mountains) Daily Award — Design

**Date:** 2026-07-21
**Status:** Approved (design); pending spec review

## Purpose

Add a second daily jersey award alongside the existing green jersey: the
**Polka Dot** award (King of the Mountains). It rewards performance on the
last three rounds of each day — the hardest, most "mountainous" rounds —
with the final two rounds worth double.

The award gets full UI parity with green: hero stats card, players-table
season total, per-entry daily column, and a Days-page sort chip with its own
daily-win counts.

## Scoring rules

Rounds are stored 0-indexed (`rounds.idx` ∈ 0–4). Only the last three rounds
score polka points:

| Round (human) | `idx` | Pot (1st, 2nd, 3rd) |
|---------------|-------|---------------------|
| 1–2           | 0–1   | — (no points)       |
| 3             | 2     | 4, 2, 0             |
| 4             | 3     | 8, 4, 0             |
| 5             | 4     | 8, 4, 0             |

Tie-splitting is identical to green: tied players split the summed pot of the
positions they jointly occupy, integer-divided. Examples with the doubled pot
`(8, 4, 0)`: two-way tie for 1st → (8+4)//2 = 6 each; three-way tie →
(8+4+0)//3 = 4 each; two-way tie for 2nd → (4+0)//2 = 2 each.

A player's daily polka score is the sum across rounds 3–5. Maximum daily
polka score: 4 + 8 + 8 = 20.

Daily polka win ranking uses the key `(polka, cumulative, maptap)` — the same
shape as green's `(green, cumulative, maptap)`.

## Approach

Generalize the existing green machinery rather than duplicating it (approach
A of the brainstorm). Green and polka differ only in the per-round points
schedule; tie-splitting, day aggregation, season totals, and win counting are
shared.

## Components

### `metrics.py`

Private generalized machinery:

- `_round_points(scores, pot)` — renamed from `_round_green_points`;
  tie-splitting logic unchanged, points pot injected as a parameter.
- `_points_by_day(conn, schedule)` — generalizes `green_points_by_day`.
  `schedule: dict[int, tuple[int, int, int]]` maps round `idx` → pot; rounds
  whose `idx` is absent from the schedule score nothing.
- `_jersey_totals(by_day)` — extracted from `green_jersey_totals`; sums a
  by-day mapping into season totals per player.
- `_jersey_win_counts(conn, points_by_day)` — extracted from
  `green_jersey_win_counts`; rank key `(points, cumulative, maptap)`.

Schedules:

- `_GREEN_SCHEDULE = {idx: (4, 2, 0) for idx in range(5)}`
- `_POLKA_SCHEDULE = {2: (4, 2, 0), 3: (8, 4, 0), 4: (8, 4, 0)}`

Public API (names describe what they return, per project convention):

- Existing `green_points_by_day`, `green_jersey_totals`,
  `green_jersey_win_counts` remain as thin wrappers over the generalized
  machinery — no caller churn, existing tests pass unchanged.
- New siblings: `polka_points_by_day`, `polka_jersey_totals`,
  `polka_jersey_win_counts`.

Threaded through the read models:

- `all_entries`: each entry gains a `"polka"` field (daily polka points).
- `daily_leaderboard`: each standing gains `"polka"`.
- `player_summary`: each row gains `"polka_points"` (season total).
- `hero_stats`: gains `"polka_leader"` and `"polka_leader_total"`, computed
  the same way as the green leader (max total, ties broken alphabetically).
- `_DAILY_SORT_KEYS` gains
  `"polka": (-polka, -cumulative, -maptap_score, player)`.

Missing-data behaviour: polka lookups use `.get(...)` defaults of `0`/`{}` so
a day or player with no scoring rounds in the schedule renders as 0 rather
than raising.

### `app.py`

`/days` accepts `sort=polka` (alongside `cumulative` and `green`); the
daily-wins panel uses `polka_jersey_win_counts` for that sort, mirroring the
existing green branch.

### Templates (full parity with green)

- `base.html` — hero stats card "Polka Dot Leader" with season total,
  alongside the Green Jersey Leader card.
- `players.html` — sortable "Polka Pts" numeric column after "Green Pts".
- `index.html` — "Polka" numeric column beside "Green" in the all-entries
  table.
- `days.html` — "Polka" sort chip (`/days?sort=polka`), "Polka" column in
  each day table, and the daily-wins chip label names the active jersey
  (Yellow / Green / Polka).

## Testing

Pytest, parameterized where natural (project preference):

1. **Refactor safety** — the existing green test suite passes unchanged
   through the new wrappers.
2. **`_round_points`** — parameterized over both pots `(4, 2, 0)` and
   `(8, 4, 0)`: clean 1st/2nd/3rd rankings and the tie cases (two-way tie
   for 1st, three-way tie, tie for 2nd), including the 6-each doubled-pot
   split.
3. **`polka_points_by_day`** — rounds 1–2 contribute nothing; a day's total
   composes correctly across rounds 3–5.
4. **`polka_jersey_totals`** — sums across days.
5. **`polka_jersey_win_counts`** — win attribution incl. the
   `(polka, cumulative, maptap)` tie-break chain.
6. **`daily_leaderboard(sort="polka")`** — ordering by the polka sort key.
7. **App routes** — `/days?sort=polka` renders with the polka chip active
   and polka win counts; invalid sorts still fall back as before.
8. **`hero_stats`** — polka leader fields present and correct.
9. **Read models** — `all_entries` / `player_summary` expose the new
   fields.

## Out of scope

- No changes to green scoring, yellow (cumulative) ranking, or the import
  pipeline.
- No historical recalculation step needed: polka is derived on read from
  existing round data, so all past days get polka scores automatically.
