import datetime

from maptap.db import connect, upsert_entries
from maptap.models import Entry, Round


def _entry(player, maptap, scores):
    return Entry(
        player=player,
        game_date=datetime.date(2026, 6, 15),
        maptap_score=maptap,
        rounds=tuple(Round(score=s, emoji="🎯") for s in scores),
    )


def test_upsert_inserts_entry_and_rounds():
    conn = connect()
    upsert_entries(conn, [_entry("Dan", 938, [100, 99, 98, 95, 86])])
    entries = conn.execute("SELECT player, maptap_score FROM entries").fetchall()
    rounds = conn.execute("SELECT score FROM rounds ORDER BY idx").fetchall()
    assert [dict(r) for r in entries] == [{"player": "Dan", "maptap_score": 938}]
    assert [r["score"] for r in rounds] == [100, 99, 98, 95, 86]


def test_upsert_is_idempotent_on_player_and_date():
    conn = connect()
    entry = _entry("Dan", 938, [100, 99, 98, 95, 86])
    upsert_entries(conn, [entry])
    upsert_entries(conn, [entry])
    count = conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
    rounds = conn.execute("SELECT COUNT(*) AS n FROM rounds").fetchone()["n"]
    assert count == 1
    assert rounds == 5


def test_upsert_updates_existing_day():
    conn = connect()
    upsert_entries(conn, [_entry("Dan", 938, [100, 99, 98, 95, 86])])
    upsert_entries(conn, [_entry("Dan", 999, [100, 100, 100, 100, 100])])
    row = conn.execute("SELECT maptap_score FROM entries").fetchone()
    rounds = conn.execute("SELECT score FROM rounds ORDER BY idx").fetchall()
    assert row["maptap_score"] == 999
    assert [r["score"] for r in rounds] == [100, 100, 100, 100, 100]
