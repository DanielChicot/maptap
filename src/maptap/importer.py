import argparse
import pathlib

from maptap.db import connect, upsert_entries
from maptap.parser import entries_from_text


def import_file(path: str, db_path: str) -> int:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    entries = entries_from_text(text)
    conn = connect(db_path)
    upsert_entries(conn, entries)
    conn.close()
    return len(entries)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Import a Map Tappers WhatsApp export")
    parser.add_argument("export", help="path to the exported chat .txt")
    parser.add_argument("--db", default="maptap.db", help="SQLite database path")
    args = parser.parse_args(argv)
    count = import_file(args.export, args.db)
    print(f"Imported {count} entries into {args.db}")


if __name__ == "__main__":
    main()
