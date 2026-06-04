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


def tool_marker(block: dict) -> str:
    name = block.get("name", "?")
    inp = block.get("input", {}) or {}
    for k in ("description", "command", "file_path", "prompt", "query", "pattern"):
        v = inp.get(k)
        if v:
            v = " ".join(str(v).split())
            if len(v) > 100:
                v = v[:100] + "…"
            return f"    → {name}: {v}"
    return f"    → {name}"


def user_text(msg: dict) -> str:
    c = msg.get("content")
    if isinstance(c, str):
        return c.strip()
    parts = []
    for b in c or []:
        if isinstance(b, dict) and b.get("type") == "text":
            parts.append(b.get("text", ""))
    return "\n".join(parts).strip()


def assistant_lines(msg: dict) -> list[str]:
    out = []
    for b in msg.get("content") or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            t = b.get("text", "").strip()
            if t:
                out.append(t)
        elif b.get("type") == "tool_use":
            out.append(tool_marker(b))
    return out


def dump_session(project_dir: Path, session_id: str, out_path: Path | None) -> int:
    """Write a clean, readable dump of a session transcript.

    Keeps real user-typed text, assistant text, and compact one-line tool
    markers. Drops assistant `thinking` and raw tool_result payloads. Groups
    consecutive assistant records into a single response block.
    """
    src = project_dir / f"{session_id}.jsonl"
    if not src.is_file():
        print(f"Session not found: {session_id}", file=sys.stderr)
        return 1
    out = out_path or Path(f"{session_id}.txt")

    rows = []  # (role, ts, body)
    with src.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            typ = rec.get("type")
            if typ not in ("user", "assistant"):
                continue
            ts = (rec.get("timestamp") or "")[:19].replace("T", " ")
            msg = rec.get("message", {})
            if typ == "user":
                body = user_text(msg)
                if body:
                    rows.append(("USER", ts, body))
            else:
                lines = assistant_lines(msg)
                if lines:
                    rows.append(("ASSISTANT", ts, "\n".join(lines)))

    # Merge consecutive ASSISTANT rows into one block (keep first ts).
    merged = []
    for role, ts, body in rows:
        if merged and role == "ASSISTANT" and merged[-1][0] == "ASSISTANT":
            merged[-1] = (role, merged[-1][1], merged[-1][2] + "\n" + body)
        else:
            merged.append((role, ts, body))

    with out.open("w") as o:
        for role, ts, body in merged:
            o.write(f"\n{'─'*6} [{ts}] {role} {'─'*6}\n{body}\n")

    print(f"{len(merged)} turns written to {out}")
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
    group.add_argument(
        "-d",
        metavar="SESSION_ID",
        help="dump a session's conversation to SESSION_ID.txt (or -o FILE)",
    )
    parser.add_argument(
        "-o",
        metavar="FILE",
        help="output file for -d (default: SESSION_ID.txt in the current dir)",
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
    if args.d:
        out_path = Path(args.o) if args.o else None
        return dump_session(project_dir, args.d, out_path)
    if "all" in args.r:
        return remove_all(project_dir, cwd)
    ret = 0
    for sid in args.r:
        ret |= remove_one(project_dir, sid)
    return ret


if __name__ == "__main__":
    sys.exit(main())
