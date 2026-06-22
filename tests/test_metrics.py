import pathlib

from maptap.db import connect, upsert_entries
from maptap.metrics import all_entries, daily_leaderboard, player_summary
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
    conn = connect()
    text = pathlib.Path("WhatsApp Chat with Map Tappers.txt").read_text(encoding="utf-8")
    upsert_entries(conn, entries_from_text(text))
    rows = all_entries(conn)

    top = rows[0]
    assert top["player"] == "Daniel Chicot"
    assert top["maptap_score"] == 987

    four_hundred_entries = [r for r in rows if r["player"] == "Finn Risdon" and r["hundreds"] == 4]
    assert len(four_hundred_entries) == 2
