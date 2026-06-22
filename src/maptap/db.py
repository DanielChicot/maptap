import sqlite3
from collections.abc import Iterable

from maptap.models import Entry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    player TEXT NOT NULL,
    game_date TEXT NOT NULL,
    maptap_score INTEGER NOT NULL,
    UNIQUE (player, game_date)
);
CREATE TABLE IF NOT EXISTS rounds (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    score INTEGER NOT NULL,
    emoji TEXT NOT NULL,
    PRIMARY KEY (entry_id, idx)
);
"""


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def upsert_entries(conn: sqlite3.Connection, entries: Iterable[Entry]) -> None:
    for entry in entries:
        cur = conn.execute(
            """
            INSERT INTO entries (player, game_date, maptap_score)
            VALUES (?, ?, ?)
            ON CONFLICT (player, game_date)
            DO UPDATE SET maptap_score = excluded.maptap_score
            RETURNING id
            """,
            (entry.player, entry.game_date.isoformat(), entry.maptap_score),
        )
        entry_id = cur.fetchone()["id"]
        conn.execute("DELETE FROM rounds WHERE entry_id = ?", (entry_id,))
        conn.executemany(
            "INSERT INTO rounds (entry_id, idx, score, emoji) VALUES (?, ?, ?, ?)",
            [
                (entry_id, i, r.score, r.emoji)
                for i, r in enumerate(entry.rounds)
            ],
        )
    conn.commit()
