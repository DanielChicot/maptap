import datetime
import pathlib

import pytest

from maptap.db import connect, upsert_entries
from maptap.metrics import (
    all_entries,
    daily_leaderboard,
    daily_win_counts,
    green_jersey_totals,
    green_jersey_win_counts,
    green_points_by_day,
    hero_stats,
    player_summary,
    polka_jersey_totals,
    polka_jersey_win_counts,
    polka_points_by_day,
)
from maptap.models import Entry, Round
from maptap.parser import entries_from_text
from tests.conftest import SAMPLE_EXPORT


def _conn():
    conn = connect()
    upsert_entries(conn, entries_from_text(SAMPLE_EXPORT))
    return conn


def test_all_entries_default_sorted_by_cumulative_desc():
    rows = all_entries(_conn())
    scores = [r["cumulative"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 485


def test_all_entries_includes_derived_fields():
    rows = all_entries(_conn())
    dan = next(r for r in rows if r["player"] == "Daniel Chicot")
    assert dan["cumulative"] == 478
    assert dan["hundreds"] == 1
    assert dan["green"] == 13
    assert dan["rounds"] == [100, 99, 98, 95, 86]


def test_player_summary_personal_best():
    summary = {r["player"]: r for r in player_summary(_conn())}
    assert summary["Finn Risdon"]["best"] == 955
    assert summary["Daniel Chicot"]["days_played"] == 1


@pytest.mark.parametrize(
    ("player", "expected"),
    [
        ("Finn Risdon", 485),
        ("Daniel Chicot", 478),
        ("Steve Risdon", 413),
    ],
)
def test_player_summary_best_cumulative(player, expected):
    summary = {r["player"]: r for r in player_summary(_conn())}
    assert summary[player]["best_cumulative"] == expected


def test_daily_leaderboard_ranks_per_day():
    days = {d["game_date"]: d for d in daily_leaderboard(_conn())}
    june15 = days["2026-06-15"]
    assert june15["standings"][0]["player"] == "Finn Risdon"
    assert june15["standings"][0]["position"] == 1
    assert june15["standings"][1]["player"] == "Daniel Chicot"


def test_hero_stats_cumulative_leader():
    stats = hero_stats(_conn())
    assert stats["cumulative_leader"] == "Finn Risdon"
    assert stats["cumulative_leader_total"] == 862


@pytest.mark.parametrize(
    ("today", "week_best", "week_best_player", "last_week_best", "last_week_best_player"),
    [
        # Friday of the Sun 14 - Sat 20 week containing all entries; prior week is empty.
        (datetime.date(2026, 6, 19), 485, "Finn Risdon", None, None),
        # Sunday starts a new week: entries roll over to "last week" immediately.
        (datetime.date(2026, 6, 21), None, None, 485, "Finn Risdon"),
        # Monday of the following week: entries still in "last week".
        (datetime.date(2026, 6, 22), None, None, 485, "Finn Risdon"),
    ],
)
def test_hero_stats_weekly_bests(today, week_best, week_best_player, last_week_best, last_week_best_player):
    stats = hero_stats(_conn(), today=today)
    assert stats["week_best"] == week_best
    assert stats["week_best_player"] == week_best_player
    assert stats["last_week_best"] == last_week_best
    assert stats["last_week_best_player"] == last_week_best_player


def test_hero_stats_green_jersey_leader():
    stats = hero_stats(_conn())
    assert stats["green_leader"] == "Finn Risdon"
    assert stats["green_leader_total"] == 37


def test_hero_stats_highest_cumulative():
    stats = hero_stats(_conn())
    assert stats["highest_cumulative"] == 485
    assert stats["highest_cumulative_player"] == "Finn Risdon"


def test_daily_leaderboard_includes_cumulative():
    days = {d["game_date"]: d for d in daily_leaderboard(_conn())}
    june15 = days["2026-06-15"]
    assert june15["standings"][0]["cumulative"] == 485
    assert june15["standings"][1]["cumulative"] == 478


def _split_winner_conn():
    conn = connect()
    upsert_entries(
        conn,
        [
            Entry(
                "MapTap Ace",
                datetime.date(2026, 6, 21),
                900,
                tuple(Round(s, "🎯") for s in (80, 80, 80, 80, 80)),
            ),
            Entry(
                "Cume Ace",
                datetime.date(2026, 6, 21),
                800,
                tuple(Round(s, "🎯") for s in (90, 90, 90, 90, 90)),
            ),
        ],
    )
    return conn


@pytest.mark.parametrize(
    ("sort", "expected_order"),
    [
        ("cumulative", ["Cume Ace", "MapTap Ace"]),
        ("maptap", ["MapTap Ace", "Cume Ace"]),
    ],
)
def test_daily_leaderboard_sort_order(sort, expected_order):
    days = daily_leaderboard(_split_winner_conn(), sort=sort)
    assert [s["player"] for s in days[0]["standings"]] == expected_order
    assert [s["position"] for s in days[0]["standings"]] == [1, 2]


def test_daily_leaderboard_cumulative_ties_break_on_maptap():
    conn = connect()
    upsert_entries(
        conn,
        [
            Entry(
                "Aaron Alphabetical",
                datetime.date(2026, 6, 21),
                840,
                tuple(Round(s, "🎯") for s in (90, 90, 90, 90, 90)),
            ),
            Entry(
                "Zoe Zenith",
                datetime.date(2026, 6, 21),
                864,
                tuple(Round(s, "🎯") for s in (90, 90, 90, 90, 90)),
            ),
        ],
    )
    days = daily_leaderboard(conn)
    assert [s["player"] for s in days[0]["standings"]] == ["Zoe Zenith", "Aaron Alphabetical"]


@pytest.mark.parametrize(
    ("metric", "expected"),
    [
        ("cumulative", {"Cume Ace": 1, "MapTap Ace": 0}),
        ("maptap", {"MapTap Ace": 1, "Cume Ace": 0}),
    ],
)
def test_daily_win_counts_follow_metric(metric, expected):
    counts = {r["player"]: r["wins"] for r in daily_win_counts(_split_winner_conn(), metric=metric)}
    assert counts == expected


@pytest.mark.parametrize(
    ("player", "expected"),
    [
        ("Finn Risdon", 2),
        ("Steve Risdon", 1),
        ("Daniel Chicot", 0),
    ],
)
def test_daily_win_counts_over_sample_export(player, expected):
    counts = {r["player"]: r["wins"] for r in daily_win_counts(_conn())}
    assert counts[player] == expected


def test_daily_win_counts_ordered_by_wins_then_player():
    players = [r["player"] for r in daily_win_counts(_conn())]
    assert players == ["Finn Risdon", "Steve Risdon", "Daniel Chicot"]


@pytest.mark.parametrize(
    ("metric", "entries", "expected"),
    [
        (
            "cumulative",
            [("Tie Breaker", 900, 90), ("Tied Loser", 800, 90)],
            {"Tie Breaker": 1, "Tied Loser": 0},
        ),
        (
            "maptap",
            [("Tie Breaker", 900, 90), ("Tied Loser", 900, 80)],
            {"Tie Breaker": 1, "Tied Loser": 0},
        ),
    ],
)
def test_daily_win_counts_tie_broken_by_other_metric(metric, entries, expected):
    conn = connect()
    upsert_entries(conn, [_make_entry(p, m, round_score=r) for p, m, r in entries])
    counts = {r["player"]: r["wins"] for r in daily_win_counts(conn, metric=metric)}
    assert counts == expected


def test_daily_win_counts_exact_tie_credits_both_players():
    conn = connect()
    upsert_entries(conn, [
        _make_entry("Alice", 900),
        _make_entry("Bob", 900),
    ])
    counts = {r["player"]: r["wins"] for r in daily_win_counts(conn, metric="cumulative")}
    assert counts == {"Alice": 1, "Bob": 1}


@pytest.mark.parametrize(
    ("player", "expected_wins"),
    [
        ("Cume Ace", 1),
        ("MapTap Ace", 0),
    ],
)
def test_player_summary_wins_use_cumulative_metric(player, expected_wins):
    summary = {r["player"]: r for r in player_summary(_split_winner_conn())}
    assert summary[player]["wins"] == expected_wins


def _entry_with_rounds(player, maptap_score, scores, game_date=datetime.date(2026, 6, 15)):
    rounds = tuple(Round(score=s, emoji="🎯") for s in scores)
    return Entry(player=player, game_date=game_date, maptap_score=maptap_score, rounds=rounds)


@pytest.mark.parametrize(
    ("game_date", "player", "expected"),
    [
        ("2026-06-15", "Finn Risdon", 17),
        ("2026-06-15", "Daniel Chicot", 13),
        ("2026-06-19", "Steve Risdon", 20),
        ("2026-06-20", "Finn Risdon", 20),
    ],
)
def test_green_points_by_day_over_sample_export(game_date, player, expected):
    points = green_points_by_day(_conn())
    assert points[game_date][player] == expected


def test_green_points_two_way_tie_for_first_splits_to_three_each():
    conn = connect()
    upsert_entries(conn, [
        _entry_with_rounds("Alice", 900, [100, 100, 100, 100, 100]),
        _entry_with_rounds("Bob", 880, [100, 100, 100, 100, 100]),
        _entry_with_rounds("Carol", 800, [90, 90, 90, 90, 90]),
    ])
    points = green_points_by_day(conn)["2026-06-15"]
    assert points == {"Alice": 15, "Bob": 15, "Carol": 0}


def test_green_points_three_way_tie_splits_to_two_each():
    conn = connect()
    upsert_entries(conn, [
        _entry_with_rounds("Alice", 900, [90, 90, 90, 90, 90]),
        _entry_with_rounds("Bob", 880, [90, 90, 90, 90, 90]),
        _entry_with_rounds("Carol", 800, [90, 90, 90, 90, 90]),
    ])
    points = green_points_by_day(conn)["2026-06-15"]
    assert points == {"Alice": 10, "Bob": 10, "Carol": 10}


def test_green_points_tie_for_second_splits_to_one_each():
    conn = connect()
    upsert_entries(conn, [
        _entry_with_rounds("Alice", 900, [100, 100, 100, 100, 100]),
        _entry_with_rounds("Bob", 880, [90, 90, 90, 90, 90]),
        _entry_with_rounds("Carol", 800, [90, 90, 90, 90, 90]),
    ])
    points = green_points_by_day(conn)["2026-06-15"]
    assert points == {"Alice": 20, "Bob": 5, "Carol": 5}


@pytest.mark.parametrize(
    ("player", "expected"),
    [
        ("Finn Risdon", 37),
        ("Steve Risdon", 20),
        ("Daniel Chicot", 13),
    ],
)
def test_green_jersey_totals_over_sample_export(player, expected):
    assert green_jersey_totals(_conn())[player] == expected


@pytest.mark.parametrize(
    ("player", "expected"),
    [
        ("Finn Risdon", 2),
        ("Steve Risdon", 1),
        ("Daniel Chicot", 0),
    ],
)
def test_green_jersey_win_counts_over_sample_export(player, expected):
    counts = {r["player"]: r["wins"] for r in green_jersey_win_counts(_conn())}
    assert counts[player] == expected


def test_green_jersey_win_tie_broken_by_cumulative():
    conn = connect()
    upsert_entries(conn, [
        _entry_with_rounds("Green Tied Low", 900, [100, 80, 90, 90, 90]),
        _entry_with_rounds("Green Tied High", 880, [90, 100, 90, 90, 90]),
    ])
    counts = {r["player"]: r["wins"] for r in green_jersey_win_counts(conn)}
    assert counts == {"Green Tied High": 1, "Green Tied Low": 0}


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


def test_daily_leaderboard_standings_include_green_points():
    days = {d["game_date"]: d for d in daily_leaderboard(_conn())}
    june15 = days["2026-06-15"]
    assert june15["standings"][0]["green"] == 17
    assert june15["standings"][1]["green"] == 13


def test_player_summary_includes_green_points():
    summary = {r["player"]: r for r in player_summary(_conn())}
    assert summary["Finn Risdon"]["green_points"] == 37
    assert summary["Daniel Chicot"]["green_points"] == 13


def test_player_summary_ranked_by_total_cumulative():
    players = [r["player"] for r in player_summary(_split_winner_conn())]
    assert players == ["Cume Ace", "MapTap Ace"]


def test_daily_leaderboard_green_sort_ranks_by_green_points():
    conn = connect()
    upsert_entries(conn, [
        _entry_with_rounds("Sprinter", 700, [60, 60, 60, 0, 0]),
        _entry_with_rounds("Steady", 800, [50, 50, 50, 100, 100]),
    ])
    green_order = [s["player"] for s in daily_leaderboard(conn, sort="green")[0]["standings"]]
    yellow_order = [s["player"] for s in daily_leaderboard(conn)[0]["standings"]]
    assert green_order == ["Sprinter", "Steady"]
    assert yellow_order == ["Steady", "Sprinter"]


def test_daily_leaderboard_defaults_to_cumulative_order():
    days = daily_leaderboard(_split_winner_conn())
    assert days[0]["standings"][0]["player"] == "Cume Ace"


def test_full_export_structural_invariants():
    export_path = pathlib.Path(__file__).resolve().parent.parent / "WhatsApp Chat with Map Tappers.txt"
    if not export_path.exists():
        pytest.skip("real export not present")
    conn = connect()
    text = export_path.read_text(encoding="utf-8")
    upsert_entries(conn, entries_from_text(text))
    rows = all_entries(conn)

    assert rows
    assert {r["player"] for r in rows} <= {"Daniel Chicot", "Steve Risdon", "Finn Risdon"}
    assert rows[0]["cumulative"] == max(r["cumulative"] for r in rows)
    for row in rows:
        assert len(row["rounds"]) == 5
        assert all(isinstance(score, int) and score >= 0 for score in row["rounds"])
        assert row["cumulative"] == sum(row["rounds"])
        assert row["hundreds"] == sum(1 for score in row["rounds"] if score == 100)
        assert row["maptap_score"] > 0


def _make_entry(player, maptap_score, game_date=datetime.date(2026, 6, 15), round_score=100):
    rounds = tuple(Round(score=round_score, emoji="🎯") for _ in range(5))
    return Entry(player=player, game_date=game_date, maptap_score=maptap_score, rounds=rounds)


def test_wins_exact_tie_credits_both_players():
    conn = connect()
    upsert_entries(conn, [
        _make_entry("Alice", 900, round_score=100),
        _make_entry("Bob", 900, round_score=100),
        _make_entry("Carol", 800, round_score=90),
    ])
    summary = {r["player"]: r for r in player_summary(conn)}
    assert summary["Alice"]["wins"] == 1
    assert summary["Bob"]["wins"] == 1
    assert summary["Carol"]["wins"] == 0


def test_wins_cumulative_tie_goes_to_higher_maptap():
    conn = connect()
    upsert_entries(conn, [
        _make_entry("Alice", 900, round_score=100),
        _make_entry("Bob", 880, round_score=100),
    ])
    summary = {r["player"]: r for r in player_summary(conn)}
    assert summary["Alice"]["wins"] == 1
    assert summary["Bob"]["wins"] == 0


def test_hero_stats_over_sample_export():
    stats = hero_stats(_conn())
    assert stats["days_tracked"] == 3
    assert stats["highest_maptap"] == 955
    assert stats["highest_maptap_player"] == "Finn Risdon"
    assert stats["leader"] == "Finn Risdon"
    assert stats["leader_total"] == 1788
    assert stats["total_hundreds"] == 6


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


def test_hero_stats_empty_database():
    stats = hero_stats(connect())
    assert stats == {
        "days_tracked": 0,
        "highest_maptap": None,
        "highest_maptap_player": None,
        "leader": None,
        "leader_total": None,
        "cumulative_leader": None,
        "cumulative_leader_total": None,
        "green_leader": None,
        "green_leader_total": None,
        "polka_leader": None,
        "polka_leader_total": None,
        "highest_cumulative": None,
        "highest_cumulative_player": None,
        "week_best": None,
        "week_best_player": None,
        "last_week_best": None,
        "last_week_best_player": None,
        "total_hundreds": 0,
    }
