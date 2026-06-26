import datetime
import pathlib

import pytest

from maptap.db import connect, upsert_entries
from maptap.metrics import all_entries, daily_leaderboard, hero_stats, player_summary
from maptap.models import Entry, Round
from maptap.parser import entries_from_text
from tests.conftest import SAMPLE_EXPORT


def _conn():
    conn = connect()
    upsert_entries(conn, entries_from_text(SAMPLE_EXPORT))
    return conn


def test_all_entries_default_sorted_by_maptap_desc():
    rows = all_entries(_conn())
    scores = [r["maptap_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 955


def test_all_entries_includes_derived_fields():
    rows = all_entries(_conn())
    dan = next(r for r in rows if r["player"] == "Daniel Chicot")
    assert dan["cumulative"] == 478
    assert dan["hundreds"] == 1
    assert dan["rounds"] == [100, 99, 98, 95, 86]


def test_player_summary_personal_best():
    summary = {r["player"]: r for r in player_summary(_conn())}
    assert summary["Finn Risdon"]["best"] == 955
    assert summary["Daniel Chicot"]["days_played"] == 1


def test_daily_leaderboard_ranks_per_day():
    days = {d["game_date"]: d for d in daily_leaderboard(_conn())}
    june15 = days["2026-06-15"]
    assert june15["standings"][0]["player"] == "Finn Risdon"
    assert june15["standings"][0]["position"] == 1
    assert june15["standings"][1]["player"] == "Daniel Chicot"


def test_known_facts_from_full_export():
    export_path = pathlib.Path(__file__).resolve().parent.parent / "WhatsApp Chat with Map Tappers.txt"
    if not export_path.exists():
        pytest.skip("real export not present")
    conn = connect()
    text = export_path.read_text(encoding="utf-8")
    upsert_entries(conn, entries_from_text(text))
    rows = all_entries(conn)

    top = rows[0]
    assert top["player"] == "Daniel Chicot"
    assert top["maptap_score"] == 987

    four_hundred_entries = [r for r in rows if r["player"] == "Finn Risdon" and r["hundreds"] == 4]
    assert len(four_hundred_entries) == 2


def _make_entry(player, maptap_score, game_date=datetime.date(2026, 6, 15)):
    rounds = tuple(Round(score=100, emoji="🎯") for _ in range(5))
    return Entry(player=player, game_date=game_date, maptap_score=maptap_score, rounds=rounds)


def test_wins_tie_credits_both_players():
    conn = connect()
    upsert_entries(conn, [
        _make_entry("Alice", 900),
        _make_entry("Bob", 900),
        _make_entry("Carol", 800),
    ])
    summary = {r["player"]: r for r in player_summary(conn)}
    assert summary["Alice"]["wins"] == 1
    assert summary["Bob"]["wins"] == 1
    assert summary["Carol"]["wins"] == 0


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
