#!/usr/bin/env python3
"""Migrate a Claude Code session to a different working directory.

Usage:
    python switch_workspace.py <target_path> [--session-id <uuid>]
    python switch_workspace.py --list          # list recent workspaces
    python switch_workspace.py                 # interactive: pick from recent workspaces

If --session-id is not provided, uses the most recently modified session
in the current project directory.

Prints the resume command to stdout on success. All status messages go to stderr.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def get_claude_projects_dir() -> Path:
    """Return the Claude Code projects directory."""
    return Path.home() / ".claude" / "projects"


def encode_path(p: Path) -> str:
    """Encode an absolute path into Claude Code's project directory name.

    Encoding rule:
      Windows: D:\\GitProjects\\foo  →  D--GitProjects-foo
      Unix:    /home/user/foo       →  -home-user-foo
    """
    # Resolve to absolute
    p = p.resolve()
    s = str(p)

    if platform.system() == "Windows":
        # D:\\GitProjects\\foo → D--GitProjects-foo
        # Replace :\\ or :/ with --
        s = s.replace(":\\", "--").replace(":/", "--")
        # Replace remaining \\ and / with -
        s = s.replace("\\", "-").replace("/", "-")
    else:
        # /home/user/foo → -home-user-foo
        s = s.replace("/", "-")

    return s


def decode_path(encoded: str) -> str:
    """Best-effort decode of an encoded project directory name back to a path.

    This is lossy — D--GitProjects-foo could be D:\\GitProjects\\foo or
    D:\\GitProjects-foo. We use heuristics: if it starts with a capital
    letter followed by --, it's likely a Windows drive letter.
    """
    s = encoded
    if len(s) >= 3 and s[0].isalpha() and s[1:3] == "--":
        # Windows: D--GitProjects-foo → D:\GitProjects\foo
        drive = s[0]
        rest = s[3:].replace("-", "\\")
        return f"{drive}:\\{rest}"
    elif s.startswith("-"):
        # Unix: -home-user-foo → /home/user/foo
        return s.replace("-", "/")
    else:
        return s.replace("-", "/")


def list_workspaces(projects_dir: Path, exclude_encoded: str | None = None) -> list[tuple[str, str, float]]:
    """List known workspaces sorted by most recent session activity.

    Returns list of (encoded_name, decoded_path, latest_mtime).
    """
    workspaces = []
    for d in projects_dir.iterdir():
        if not d.is_dir() or d.name == "memory":
            continue
        if exclude_encoded and d.name == exclude_encoded:
            continue
        # Find most recent jsonl
        jsonl_files = list(d.glob("*.jsonl"))
        if not jsonl_files:
            continue
        latest_mtime = max(f.stat().st_mtime for f in jsonl_files)
        decoded = decode_path(d.name)
        workspaces.append((d.name, decoded, latest_mtime))

    workspaces.sort(key=lambda x: x[2], reverse=True)
    return workspaces


def find_current_project_dir(projects_dir: Path, cwd: Path) -> Path | None:
    """Find the project directory for the given cwd."""
    encoded = encode_path(cwd)
    candidate = projects_dir / encoded
    if candidate.is_dir():
        return candidate
    return None


def find_latest_session(project_dir: Path) -> tuple[Path, str] | None:
    """Find the most recently modified .jsonl in a project directory.

    Returns (jsonl_path, session_id) or None.
    """
    jsonl_files = list(project_dir.glob("*.jsonl"))
    if not jsonl_files:
        return None
    latest = max(jsonl_files, key=lambda f: f.stat().st_mtime)
    session_id = latest.stem
    return latest, session_id


def get_last_uuid(jsonl_path: Path) -> str:
    """Read the last line of a JSONL file and extract its uuid."""
    with open(jsonl_path, encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        return ""
    last = json.loads(lines[-1])
    return last.get("uuid", "")


def copy_session(
    source_jsonl: Path,
    session_id: str,
    target_project_dir: Path,
) -> Path:
    """Copy session JSONL and subagents directory to target."""
    target_project_dir.mkdir(parents=True, exist_ok=True)

    # Copy JSONL
    target_jsonl = target_project_dir / source_jsonl.name
    shutil.copy2(source_jsonl, target_jsonl)
    print(f"  Copied session JSONL", file=sys.stderr)

    # Copy subagents directory if it exists
    subagents = source_jsonl.parent / session_id
    if subagents.is_dir():
        target_subagents = target_project_dir / session_id
        if target_subagents.exists():
            shutil.rmtree(target_subagents)
        shutil.copytree(subagents, target_subagents)
        print(f"  Copied subagents directory", file=sys.stderr)

    return target_jsonl


def append_context_note(
    jsonl_path: Path,
    source_cwd: str,
    target_path: str,
) -> None:
    """Append a migration context note to the JSONL."""
    last_uuid = get_last_uuid(jsonl_path)
    new_uuid = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    record = {
        "parentUuid": last_uuid,
        "isSidechain": False,
        "type": "user",
        "message": {
            "role": "user",
            "content": (
                f"[System note: This session was migrated from {source_cwd} "
                f"to {target_path}. The working directory is now {target_path}. "
                f"File paths from earlier in this conversation may reference "
                f"{source_cwd} — adjust them to the new location as needed. "
                f"The project context (CLAUDE.md, git status, etc.) now reflects "
                f"{target_path}.]"
            ),
        },
        "uuid": new_uuid,
        "userType": "external",
        "timestamp": timestamp,
    }

    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write("\n" + json.dumps(record, ensure_ascii=False))

    print(f"  Appended migration context note", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate a Claude Code session to a different working directory."
    )
    parser.add_argument("target_path", nargs="?", default=None,
                        help="Absolute path to the target directory. If omitted, shows interactive picker.")
    parser.add_argument("--session-id", help="Session ID (UUID). Auto-detected if omitted.")
    parser.add_argument("--cwd", help="Override current working directory for source lookup.")
    parser.add_argument("--list", action="store_true", help="List recent workspaces and exit.")
    args = parser.parse_args()

    source_cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    projects_dir = get_claude_projects_dir()
    current_encoded = encode_path(source_cwd)

    # --list mode: just print workspaces
    if args.list:
        workspaces = list_workspaces(projects_dir)
        if not workspaces:
            print("No workspaces found.", file=sys.stderr)
            sys.exit(0)
        for encoded, decoded, mtime in workspaces:
            marker = " (current)" if encoded == current_encoded else ""
            ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  {decoded}{marker}  [{ts}]", file=sys.stderr)
        sys.exit(0)

    # Interactive picker if no target given
    if args.target_path is None:
        workspaces = list_workspaces(projects_dir, exclude_encoded=current_encoded)
        if not workspaces:
            print("No other workspaces found.", file=sys.stderr)
            sys.exit(1)
        print("Recent workspaces:", file=sys.stderr)
        for i, (encoded, decoded, mtime) in enumerate(workspaces):
            ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  [{i + 1}] {decoded}  [{ts}]", file=sys.stderr)
        print(f"  [0] Enter a custom path", file=sys.stderr)
        try:
            raw = input(f"  Choice [1-{len(workspaces)}, 0 for custom]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            sys.exit(1)
        if raw == "0" or raw == "":
            try:
                custom = input("  Path: ").strip()
            except (EOFError, KeyboardInterrupt):
                print(file=sys.stderr)
                sys.exit(1)
            target = Path(custom).resolve()
        else:
            try:
                idx = int(raw) - 1
                if not (0 <= idx < len(workspaces)):
                    raise ValueError
            except ValueError:
                print("Invalid choice.", file=sys.stderr)
                sys.exit(1)
            target = Path(workspaces[idx][1]).resolve()
    else:
        target = Path(args.target_path).resolve()

    if not target.is_dir():
        print(f"Error: target directory does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    source_cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    projects_dir = get_claude_projects_dir()

    # Find current project directory
    current_project = find_current_project_dir(projects_dir, source_cwd)
    if not current_project:
        print(f"Error: no Claude project directory found for: {source_cwd}", file=sys.stderr)
        print(f"  Expected: {projects_dir / encode_path(source_cwd)}", file=sys.stderr)
        sys.exit(1)

    # Find session
    if args.session_id:
        session_id = args.session_id
        source_jsonl = current_project / f"{session_id}.jsonl"
        if not source_jsonl.is_file():
            print(f"Error: session file not found: {source_jsonl}", file=sys.stderr)
            sys.exit(1)
    else:
        result = find_latest_session(current_project)
        if not result:
            print(f"Error: no sessions found in: {current_project}", file=sys.stderr)
            sys.exit(1)
        source_jsonl, session_id = result

    print(f"Source: {source_cwd}", file=sys.stderr)
    print(f"Target: {target}", file=sys.stderr)
    print(f"Session: {session_id}", file=sys.stderr)

    # Encode target and copy
    target_encoded = encode_path(target)
    target_project_dir = projects_dir / target_encoded

    # Check if target already has this session
    existing_target = target_project_dir / source_jsonl.name
    if existing_target.is_file():
        print(f"  Note: overwriting existing session in target (fresh copy from source)", file=sys.stderr)

    print(f"Copying session...", file=sys.stderr)
    target_jsonl = copy_session(source_jsonl, session_id, target_project_dir)

    # Append context note
    append_context_note(target_jsonl, str(source_cwd), str(target))

    # Output the resume command
    print(f"\nSession prepared for {target}", file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f"To switch, run:", file=sys.stderr)
    print(f"  /exit", file=sys.stderr)
    print(f'  cd "{target}" && claude --resume {session_id} --fork-session', file=sys.stderr)

    # stdout: just the session ID for capture
    print(session_id)


if __name__ == "__main__":
    main()
