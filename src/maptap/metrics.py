import datetime
import sqlite3


def all_entries(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT e.id, e.player, e.game_date, e.maptap_score,
               SUM(r.score) AS cumulative,
               SUM(CASE WHEN r.score = 100 THEN 1 ELSE 0 END) AS hundreds
        FROM entries e
        JOIN rounds r ON r.entry_id = e.id
        GROUP BY e.id
        ORDER BY cumulative DESC, e.maptap_score DESC, e.player ASC, e.game_date ASC
        """
    ).fetchall()
    green = green_points_by_day(conn)
    polka = polka_points_by_day(conn)
    result = []
    for row in rows:
        rounds = conn.execute(
            "SELECT score FROM rounds WHERE entry_id = ? ORDER BY idx", (row["id"],)
        ).fetchall()
        result.append(
            {
                "player": row["player"],
                "game_date": row["game_date"],
                "maptap_score": row["maptap_score"],
                "cumulative": row["cumulative"],
                "hundreds": row["hundreds"],
                "green": green[row["game_date"]][row["player"]],
                "polka": polka.get(row["game_date"], {}).get(row["player"], 0),
                "rounds": [r["score"] for r in rounds],
            }
        )
    return result


def player_summary(conn: sqlite3.Connection) -> list[dict]:
    base = conn.execute(
        """
        SELECT e.player,
               MAX(e.maptap_score) AS best,
               MAX(r_sum.cumulative) AS best_cumulative,
               SUM(e.maptap_score) AS total_maptap,
               SUM(r_sum.cumulative) AS total_cumulative,
               COUNT(*) AS days_played
        FROM entries e
        JOIN (
            SELECT entry_id, SUM(score) AS cumulative
            FROM rounds GROUP BY entry_id
        ) r_sum ON r_sum.entry_id = e.id
        GROUP BY e.player
        ORDER BY total_cumulative DESC
        """
    ).fetchall()

    wins = {row["player"]: row["wins"] for row in daily_win_counts(conn, metric="cumulative")}
    green = green_jersey_totals(conn)
    polka = polka_jersey_totals(conn)
    combative = combative_points_totals(conn)
    return [
        {
            "player": row["player"],
            "best": row["best"],
            "best_cumulative": row["best_cumulative"],
            "total_maptap": row["total_maptap"],
            "total_cumulative": row["total_cumulative"],
            "days_played": row["days_played"],
            "wins": wins.get(row["player"], 0),
            "green_points": green.get(row["player"], 0),
            "polka_points": polka.get(row["player"], 0),
            "combative_points": combative.get(row["player"], 0),
        }
        for row in base
    ]


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


# Combative points: your 100s for the day, plus half a point if you take the
# award on the walk-down tie-break (i.e. the day's best 100 count is shared).
def combative_points_by_day(conn: sqlite3.Connection) -> dict[str, dict[str, int | float]]:
    points: dict[str, dict[str, int | float]] = {}
    for day, keys in _combative_keys_by_day(conn).items():
        hundreds = {player: sum(1 for score in key if score == 100) for player, key in keys.items()}
        tie_broken = list(hundreds.values()).count(max(hundreds.values())) > 1
        best = max(keys.values())
        points[day] = {
            player: hundreds[player] + 0.5 if tie_broken and keys[player] == best else hundreds[player]
            for player in keys
        }
    return points


def combative_points_totals(conn: sqlite3.Connection) -> dict[str, int | float]:
    return {
        player: int(total) if total == int(total) else total
        for player, total in _jersey_totals(combative_points_by_day(conn)).items()
    }


def daily_win_counts(conn: sqlite3.Connection, metric: str = "cumulative") -> list[dict]:
    ranking = {
        "cumulative": "cumulative DESC, maptap DESC",
        "maptap": "maptap DESC, cumulative DESC",
    }[metric]
    rows = conn.execute(
        f"""
        WITH day_scores AS (
            SELECT e.player, e.game_date,
                   SUM(r.score) AS cumulative,
                   e.maptap_score AS maptap
            FROM entries e
            JOIN rounds r ON r.entry_id = e.id
            GROUP BY e.id
        )
        SELECT player,
               SUM(CASE WHEN (cumulative, maptap) = (
                   SELECT cumulative, maptap FROM day_scores d2
                   WHERE d2.game_date = d1.game_date
                   ORDER BY {ranking} LIMIT 1
               ) THEN 1 ELSE 0 END) AS wins
        FROM day_scores d1
        GROUP BY player
        ORDER BY wins DESC, player ASC
        """
    ).fetchall()
    return [{"player": row["player"], "wins": row["wins"]} for row in rows]


_DAILY_SORT_KEYS = {
    "cumulative": lambda s: (-s["cumulative"], -s["maptap_score"], s["player"]),
    "maptap": lambda s: (-s["maptap_score"], -s["cumulative"], s["player"]),
    "green": lambda s: (-s["green"], -s["cumulative"], -s["maptap_score"], s["player"]),
    "polka": lambda s: (-s["polka"], -s["cumulative"], -s["maptap_score"], s["player"]),
    "combative": lambda s: (-s["combative_points"], -s["cumulative"], -s["maptap_score"], s["player"]),
}


def daily_leaderboard(conn: sqlite3.Connection, sort: str = "cumulative") -> list[dict]:
    sort_key = _DAILY_SORT_KEYS[sort]
    rows = conn.execute(
        """
        SELECT e.game_date, e.player, e.maptap_score,
               SUM(r.score) AS cumulative
        FROM entries e
        JOIN rounds r ON r.entry_id = e.id
        GROUP BY e.id
        ORDER BY e.game_date DESC
        """
    ).fetchall()
    green = green_points_by_day(conn)
    polka = polka_points_by_day(conn)
    combative = combative_points_by_day(conn)
    by_day: dict[str, list[dict]] = {}
    for row in rows:
        by_day.setdefault(row["game_date"], []).append(
            {
                "player": row["player"],
                "maptap_score": row["maptap_score"],
                "cumulative": row["cumulative"],
                "green": green[row["game_date"]][row["player"]],
                "polka": polka.get(row["game_date"], {}).get(row["player"], 0),
                "combative_points": combative[row["game_date"]][row["player"]],
            }
        )
    for standings in by_day.values():
        standings.sort(key=sort_key)
        for position, standing in enumerate(standings, start=1):
            standing["position"] = position
    return [{"game_date": day, "standings": standings} for day, standings in by_day.items()]


def _best_yellow_between(
    conn: sqlite3.Connection, start: datetime.date, end: datetime.date
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT e.player, SUM(r.score) AS total
        FROM entries e JOIN rounds r ON r.entry_id = e.id
        WHERE e.game_date >= ? AND e.game_date < ?
        GROUP BY e.id ORDER BY total DESC, e.player ASC LIMIT 1
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchone()


def _best_points_between(
    by_day: dict[str, dict[str, int]], start: datetime.date, end: datetime.date
) -> tuple[int, str] | None:
    candidates = [
        (points, player)
        for day, players in by_day.items()
        if start.isoformat() <= day < end.isoformat()
        for player, points in players.items()
    ]
    return min(candidates, key=lambda pp: (-pp[0], pp[1])) if candidates else None


def hero_stats(conn: sqlite3.Connection, today: datetime.date | None = None) -> dict:
    highest = conn.execute(
        "SELECT player, maptap_score FROM entries "
        "ORDER BY maptap_score DESC, player ASC LIMIT 1"
    ).fetchone()

    leader = conn.execute(
        "SELECT player, SUM(maptap_score) AS total FROM entries "
        "GROUP BY player ORDER BY total DESC, player ASC LIMIT 1"
    ).fetchone()

    highest_cumulative = conn.execute(
        """
        SELECT e.player, SUM(r.score) AS total
        FROM entries e JOIN rounds r ON r.entry_id = e.id
        GROUP BY e.id ORDER BY total DESC, e.player ASC LIMIT 1
        """
    ).fetchone()

    today = today or datetime.date.today()
    # Weeks run Sunday to Saturday.
    week_start = today - datetime.timedelta(days=(today.weekday() + 1) % 7)
    last_week_start = week_start - datetime.timedelta(days=7)
    week_best = _best_yellow_between(conn, week_start, week_start + datetime.timedelta(days=7))
    last_week_best = _best_yellow_between(conn, last_week_start, week_start)
    last_week_green = _best_points_between(green_points_by_day(conn), last_week_start, week_start)
    last_week_polka = _best_points_between(polka_points_by_day(conn), last_week_start, week_start)
    last_week_awards: dict[str, int] = {}
    for day, winners in combative_riders_by_day(conn).items():
        if last_week_start.isoformat() <= day < week_start.isoformat():
            for player in winners:
                last_week_awards[player] = last_week_awards.get(player, 0) + 1
    last_week_combative = (
        min(last_week_awards.items(), key=lambda pw: (-pw[1], pw[0])) if last_week_awards else None
    )

    return {
        "highest_maptap": highest["maptap_score"] if highest else None,
        "highest_maptap_player": highest["player"] if highest else None,
        "highest_cumulative": highest_cumulative["total"] if highest_cumulative else None,
        "highest_cumulative_player": highest_cumulative["player"] if highest_cumulative else None,
        "leader": leader["player"] if leader else None,
        "leader_total": leader["total"] if leader else None,
        "week_best": week_best["total"] if week_best else None,
        "week_best_player": week_best["player"] if week_best else None,
        "last_week_best": last_week_best["total"] if last_week_best else None,
        "last_week_best_player": last_week_best["player"] if last_week_best else None,
        "last_week_best_green": last_week_green[0] if last_week_green else None,
        "last_week_best_green_player": last_week_green[1] if last_week_green else None,
        "last_week_best_polka": last_week_polka[0] if last_week_polka else None,
        "last_week_best_polka_player": last_week_polka[1] if last_week_polka else None,
        "last_week_combative": last_week_combative[1] if last_week_combative else None,
        "last_week_combative_player": last_week_combative[0] if last_week_combative else None,
    }
