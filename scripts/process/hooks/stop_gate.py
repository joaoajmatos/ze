#!/usr/bin/env python3
"""Stop hook: do not end a turn with a review verdict undelivered or a state file older than the last commit.

Exit 2 + stderr blocks the stop and becomes the agent's next instruction. stop_hook_active is respected,
so each reason blocks at most once. A no-op unless MAESTRI_TERMINAL_ID is set.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

STATE_ROLES = {"eng", "jr", "architect", "review", "qa", "docs"}


def git(cwd: str, *args: str) -> str:
    p = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def pending_reviews(repo: str) -> list[str]:
    found = []
    for path in sorted((Path(repo) / ".process" / "reviews").glob("*.json")):
        try:
            record = json.loads(path.read_text())
        except ValueError:
            continue
        if record.get("state") == "requested":
            found.append(path.name)
    return found


def state_file_stale(cwd: str, terminal_id: str) -> str:
    common = git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    committed = git(cwd, "log", "-1", "--format=%ct", "HEAD")
    if not common or not committed:
        return ""
    state = Path(common).parent / "journal" / "state" / f"{terminal_id}.md"
    if state.exists() and state.stat().st_mtime < int(committed):
        return str(state)
    return ""


def decide(payload: dict, env: dict[str, str]) -> str:
    """The reason to block, or an empty string."""
    terminal = env.get("MAESTRI_TERMINAL_ID", "")
    if not terminal or payload.get("stop_hook_active"):
        return ""
    role = env.get("ZE_ROLE", "").lower()
    cwd = payload.get("cwd") or os.getcwd()
    toplevel = git(cwd, "rev-parse", "--show-toplevel")
    repo = env.get("ZE_REVIEW_REPO") or toplevel
    if role == "review" and repo:
        pending = pending_reviews(repo)
        if pending:
            return (
                f"Review {', '.join(pending)} has no verdict record. Run "
                "make process-review-verdict RANGE=<a..b> VERDICT=APPROVE|CHANGES FINDINGS=<file> before you stop."
            )
    if role in STATE_ROLES:
        stale = state_file_stale(cwd, terminal)
        if stale:
            return f"Your state file {stale} is older than your last commit: update it (Now, Commits, Gates) before you stop."
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    reason = decide(payload, dict(os.environ))
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
