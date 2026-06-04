#!/usr/bin/env python3
"""List or remove Claude Code sessions for the current working directory."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def project_dir_for(cwd: Path) -> Path:
    encoded = str(cwd).replace("/", "-")
    return Path.home() / ".claude" / "projects" / encoded


def session_names() -> dict[str, str]:
    """Build a map of session_id -> custom name from ~/.claude/sessions/*.json."""
    names: dict[str, str] = {}
    sessions_dir = Path.home() / ".claude" / "sessions"
    if not sessions_dir.is_dir():
        return names
    for f in sessions_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if "name" in data and "sessionId" in data:
                names[data["sessionId"]] = data["name"]
        except (json.JSONDecodeError, OSError):
            continue
    return names


def ai_title(path: Path) -> str:
    with path.open() as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") == "ai-title":
                return entry.get("aiTitle", "")
    return ""


def list_sessions(project_dir: Path, cwd: Path) -> int:
    files = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not files:
        print(f"No sessions for {cwd}")
        return 0
    names = session_names()
    print(f"{'SESSION ID':38}  {'MODIFIED':19}  {'SIZE':>10}  {'MSGS':>5}  TITLE")
    for f in files:
        st = f.stat()
        mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        with f.open("rb") as fh:
            lines = sum(1 for _ in fh)
        title = names.get(f.stem) or ai_title(f)
        print(f"{f.stem:38}  {mtime:19}  {st.st_size:>10}  {lines:>5}  {title}")
    return 0


def remove_one(project_dir: Path, session_id: str) -> int:
    f = project_dir / f"{session_id}.jsonl"
    if not f.is_file():
        print(f"Session not found: {session_id}", file=sys.stderr)
        return 1
    f.unlink()
    print(f"Removed session {session_id}")
    return 0


def remove_all(project_dir: Path, cwd: Path) -> int:
    files = list(project_dir.glob("*.jsonl"))
    if not files:
        print(f"No sessions to remove for {cwd}")
        return 0
    ans = input(f"Remove {len(files)} session(s) for {cwd}? [y/N] ").strip().lower()
    if ans != "y":
        print("Aborted.")
        return 0
    for f in files:
        f.unlink()
    print(f"Removed {len(files)} session(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List or remove Claude Code sessions for the current working directory.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-l", action="store_true", help="list sessions for $PWD")
    group.add_argument(
        "-r",
        metavar="SESSION_ID",
        nargs="+",
        help="remove one or more session ids, or 'all' to remove every session for $PWD",
    )
    args = parser.parse_args()

    cwd = Path(os.getcwd()).resolve()
    project_dir = project_dir_for(cwd)

    if not project_dir.is_dir():
        print(f"No sessions directory found for {cwd}")
        print(f"  (expected: {project_dir})")
        return 0

    if args.l:
        return list_sessions(project_dir, cwd)
    if "all" in args.r:
        return remove_all(project_dir, cwd)
    ret = 0
    for sid in args.r:
        ret |= remove_one(project_dir, sid)
    return ret


if __name__ == "__main__":
    sys.exit(main())
