#!/usr/bin/env python3
"""PostToolUse(Bash) hook: stamp .process/own-commit-<terminal id> after a git commit that succeeded.

Claude Code runs PostToolUse only when the tool call succeeded (a failed command fires PostToolUseFailure),
so a refused or failed commit never leaves a stamp. stop_gate.py compares the state file with this stamp.
A no-op unless MAESTRI_TERMINAL_ID is set. It never blocks.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import guard_bash  # noqa: E402


def commit_dir(command: str, cwd: str) -> str | None:
    """The directory a `git commit` in this command line runs in, or None when it has none."""
    for raw, _ in guard_bash.segments(command):
        argv, _env = guard_bash._strip_prefix(raw)
        if argv and os.path.basename(argv[0]) == "git":
            sub, _rest, workdir = guard_bash._git_parts(argv)
            if sub == "commit":
                return os.path.join(cwd, workdir) if workdir else cwd
    return None


def stamp(where: str, terminal: str) -> bool:
    top = subprocess.run(
        ["git", "-C", where or ".", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if top.returncode:
        return False
    marker = Path(top.stdout.strip()) / ".process" / f"own-commit-{terminal}"
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(time.time()))
    except OSError:
        return False
    return True


def main() -> int:
    terminal = os.environ.get("MAESTRI_TERMINAL_ID", "")
    if not terminal:
        return 0
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    where = commit_dir(
        payload.get("tool_input", {}).get("command", ""), payload.get("cwd", "")
    )
    if where is not None:
        stamp(where, terminal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
