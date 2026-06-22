import pathlib

from fastapi.testclient import TestClient

from maptap.db import connect, upsert_entries
from maptap.parser import entries_from_text
from tests.conftest import SAMPLE_EXPORT


def _build_db(path):
    conn = connect(str(path))
    upsert_entries(conn, entries_from_text(SAMPLE_EXPORT))
    conn.close()


def test_index_lists_entries(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Daniel Chicot" in response.text
    assert "955" in response.text


def test_players_and_days_routes(tmp_path, monkeypatch):
    db = tmp_path / "maptap.db"
    _build_db(db)
    monkeypatch.setenv("MAPTAP_DB", str(db))

    from maptap.app import app

    client = TestClient(app)
    assert client.get("/players").status_code == 200
    assert client.get("/days").status_code == 200
