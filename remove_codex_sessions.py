#!/usr/bin/env python3
"""Remove Codex resumable sessions from the local Codex state store."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
STATE_DB = CODEX_HOME / "state_5.sqlite"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Delete Codex resumable sessions. By default, deletes sessions whose "
            "cwd equals the current working directory."
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="delete all Codex sessions")
    group.add_argument("--id", metavar="SESSION_ID", help="delete one session by id")
    return parser.parse_args()


def quote_table(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def existing_tables(cur: sqlite3.Cursor) -> set[str]:
    rows = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0] for row in rows}


def table_columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    return {row[1] for row in cur.execute(f"PRAGMA table_info({quote_table(table)})")}


def delete_related_rows(cur: sqlite3.Cursor, session_ids: list[str]) -> None:
    if not session_ids:
        return

    placeholders = ",".join("?" for _ in session_ids)
    candidate_columns = ("thread_id", "parent_thread_id", "child_thread_id")

    for table in sorted(existing_tables(cur) - {"threads"}):
        columns = table_columns(cur, table)
        for column in candidate_columns:
            if column not in columns:
                continue
            cur.execute(
                f"DELETE FROM {quote_table(table)} WHERE {column} IN ({placeholders})",
                session_ids,
            )


def select_sessions(cur: sqlite3.Cursor, args: argparse.Namespace) -> list[tuple[str, str]]:
    if args.all:
        rows = cur.execute("SELECT id, rollout_path FROM threads ORDER BY updated_at DESC")
    elif args.id:
        rows = cur.execute(
            "SELECT id, rollout_path FROM threads WHERE id = ?",
            (args.id,),
        )
    else:
        cwd = str(Path.cwd())
        rows = cur.execute(
            "SELECT id, rollout_path FROM threads WHERE cwd = ? ORDER BY updated_at DESC",
            (cwd,),
        )
    return [(row[0], row[1]) for row in rows]


def main() -> int:
    args = parse_args()
    if not STATE_DB.exists():
        print(f"Codex state database not found: {STATE_DB}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(STATE_DB)
    try:
        cur = conn.cursor()
        sessions = select_sessions(cur, args)
        session_ids = [session_id for session_id, _ in sessions]
        rollout_paths = [path for _, path in sessions if path]

        if not sessions:
            print("No matching Codex sessions found.")
            return 0

        delete_related_rows(cur, session_ids)
        placeholders = ",".join("?" for _ in session_ids)
        cur.execute(f"DELETE FROM threads WHERE id IN ({placeholders})", session_ids)
        deleted_threads = cur.rowcount
        conn.commit()

        deleted_files = 0
        missing_files = 0
        for rollout_path in rollout_paths:
            try:
                Path(rollout_path).unlink()
                deleted_files += 1
            except FileNotFoundError:
                missing_files += 1

        print(f"Deleted session rows: {deleted_threads}")
        print(f"Deleted rollout files: {deleted_files}")
        if missing_files:
            print(f"Rollout files already missing: {missing_files}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
