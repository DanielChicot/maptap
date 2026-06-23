from maptap.db import connect
from maptap.importer import import_file
from tests.conftest import SAMPLE_EXPORT


def test_import_file_is_idempotent(tmp_path):
    export = tmp_path / "chat.txt"
    export.write_text(SAMPLE_EXPORT, encoding="utf-8")
    db = tmp_path / "maptap.db"

    first = import_file(str(export), str(db))
    second = import_file(str(export), str(db))

    assert first == 4
    assert second == 4

    conn = connect(str(db))
    count = conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
    assert count == 4
