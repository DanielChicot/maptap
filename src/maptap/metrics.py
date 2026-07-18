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
        ORDER BY e.maptap_score DESC, e.player ASC, e.game_date ASC
        """
    ).fetchall()
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
               SUM(r_sum.hundreds) AS total_hundreds,
               COUNT(*) AS days_played
        FROM entries e
        JOIN (
            SELECT entry_id,
                   SUM(score) AS cumulative,
                   SUM(CASE WHEN score = 100 THEN 1 ELSE 0 END) AS hundreds
            FROM rounds GROUP BY entry_id
        ) r_sum ON r_sum.entry_id = e.id
        GROUP BY e.player
        ORDER BY total_cumulative DESC
        """
    ).fetchall()

    wins = {row["player"]: row["wins"] for row in daily_win_counts(conn, metric="cumulative")}
    green = green_jersey_totals(conn)
    return [
        {
            "player": row["player"],
            "best": row["best"],
            "best_cumulative": row["best_cumulative"],
            "total_maptap": row["total_maptap"],
            "total_cumulative": row["total_cumulative"],
            "total_hundreds": row["total_hundreds"],
            "days_played": row["days_played"],
            "wins": wins.get(row["player"], 0),
            "green_points": green.get(row["player"], 0),
        }
        for row in base
    ]


# Green jersey: per round, 1st scores 4, 2nd scores 2, 3rd scores 0.
# Tied players split the points of the positions they jointly occupy
# (two-way tie for first: 3 each; three-way tie: 2 each; tie for second: 1 each).
_GREEN_POINTS = (4, 2, 0)


def _round_green_points(scores: list[tuple[str, int]]) -> dict[str, int]:
    ranked = sorted(scores, key=lambda ps: ps[1], reverse=True)
    points: dict[str, int] = {}
    position = 0
    while position < len(ranked):
        tied = [player for player, score in ranked if score == ranked[position][1]]
        pot = sum(_GREEN_POINTS[position:position + len(tied)])
        for player in tied:
            points[player] = pot // len(tied)
        position += len(tied)
    return points


def green_points_by_day(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
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
    for (game_date, _), scores in rounds.items():
        day = totals.setdefault(game_date, {})
        for player, points in _round_green_points(scores).items():
            day[player] = day.get(player, 0) + points
    return totals


def green_jersey_totals(conn: sqlite3.Connection) -> dict[str, int]:
    totals: dict[str, int] = {}
    for day in green_points_by_day(conn).values():
        for player, points in day.items():
            totals[player] = totals.get(player, 0) + points
    return totals


def green_jersey_win_counts(conn: sqlite3.Connection) -> list[dict]:
    green = green_points_by_day(conn)
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
        rank_key = (green[row["game_date"]][row["player"]], row["cumulative"], row["maptap_score"])
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


def daily_leaderboard(conn: sqlite3.Connection, sort: str = "cumulative") -> list[dict]:
    sort_column = {
        "cumulative": "cumulative DESC, e.maptap_score",
        "maptap": "e.maptap_score DESC, cumulative",
    }[sort]
    rows = conn.execute(
        f"""
        SELECT e.game_date, e.player, e.maptap_score,
               SUM(r.score) AS cumulative
        FROM entries e
        JOIN rounds r ON r.entry_id = e.id
        GROUP BY e.id
        ORDER BY e.game_date DESC, {sort_column} DESC, e.player ASC
        """
    ).fetchall()
    green = green_points_by_day(conn)
    by_day: dict[str, list[dict]] = {}
    for row in rows:
        standings = by_day.setdefault(row["game_date"], [])
        standings.append(
            {
                "position": len(standings) + 1,
                "player": row["player"],
                "maptap_score": row["maptap_score"],
                "cumulative": row["cumulative"],
                "green": green[row["game_date"]][row["player"]],
            }
        )
    return [{"game_date": day, "standings": standings} for day, standings in by_day.items()]


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

    highest_cumulative = conn.execute(
        """
        SELECT e.player, SUM(r.score) AS total
        FROM entries e JOIN rounds r ON r.entry_id = e.id
        GROUP BY e.id ORDER BY total DESC, e.player ASC LIMIT 1
        """
    ).fetchone()

    cumulative_leader = conn.execute(
        """
        SELECT e.player, SUM(r.score) AS total
        FROM entries e JOIN rounds r ON r.entry_id = e.id
        GROUP BY e.player ORDER BY total DESC, e.player ASC LIMIT 1
        """
    ).fetchone()

    total_hundreds = conn.execute(
        "SELECT COUNT(*) AS n FROM rounds WHERE score = 100"
    ).fetchone()["n"]

    return {
        "days_tracked": days_tracked,
        "highest_maptap": highest["maptap_score"] if highest else None,
        "highest_maptap_player": highest["player"] if highest else None,
        "highest_cumulative": highest_cumulative["total"] if highest_cumulative else None,
        "highest_cumulative_player": highest_cumulative["player"] if highest_cumulative else None,
        "leader": leader["player"] if leader else None,
        "leader_total": leader["total"] if leader else None,
        "cumulative_leader": cumulative_leader["player"] if cumulative_leader else None,
        "cumulative_leader_total": cumulative_leader["total"] if cumulative_leader else None,
        "total_hundreds": total_hundreds,
    }
