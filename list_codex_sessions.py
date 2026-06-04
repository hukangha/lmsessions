#!/usr/bin/env python3
"""List Codex resumable sessions from the local Codex state store."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sqlite3
import sys
from pathlib import Path


CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
STATE_DB = CODEX_HOME / "state_5.sqlite"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List Codex session ids whose cwd equals the current working directory "
            "with updated time and title as TSV."
        )
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="omit the header row",
    )
    parser.add_argument(
        "--utc",
        action="store_true",
        help="format times in UTC instead of local time",
    )
    return parser.parse_args()


def format_time(timestamp_ms: int | None, timestamp: int, *, utc: bool) -> str:
    if timestamp_ms is not None:
        value = timestamp_ms / 1000
    else:
        value = timestamp

    timezone = dt.UTC if utc else None
    updated_at = dt.datetime.fromtimestamp(value, tz=timezone)
    return updated_at.isoformat(timespec="seconds")


def main() -> int:
    args = parse_args()
    if not STATE_DB.exists():
        print(f"Codex state database not found: {STATE_DB}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(STATE_DB)
    try:
        cwd = str(Path.cwd())
        rows = conn.execute(
            """
            SELECT id, title, updated_at, updated_at_ms
            FROM threads
            WHERE cwd = ?
            ORDER BY updated_at DESC
            """,
            (cwd,),
        )

        if not args.no_header:
            print("session_id\tupdated_at\ttitle")

        for session_id, title, updated_at, updated_at_ms in rows:
            time_text = format_time(updated_at_ms, updated_at, utc=args.utc)
            print(f"{session_id}\t{time_text}\t{title}")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
