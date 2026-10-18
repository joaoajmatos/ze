#!/usr/bin/env python3
"""PreToolUse guard for Edit, Write and AskUserQuestion (Claude Code hook contract).

Exit 2 + stderr blocks. A no-op unless MAESTRI_TERMINAL_ID is set; ZE_ROLE unset means unrestricted.
Rules:
  AskUserQuestion      only the Maestro asks the user; everyone else batches questions to the Maestro
  review role          read-only, except files in a scratchpad directory (findings go there)
  .process/receipts, .process/reviews   written by the process scripts only, never by hand
  new files in specs/arch/              architect and Maestro only (no working notes there)
  .process/lane.json   when present, writes must fall inside the lane's `owns` globs
"""

import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path


def toplevel(cwd: str) -> Path | None:
    p = subprocess.run(
        ["git", "-C", cwd or ".", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    return Path(p.stdout.strip()) if p.returncode == 0 else None


def in_scratchpad(path: Path) -> bool:
    return "scratchpad" in path.parts


def decide(payload: dict, env: dict[str, str]) -> str:
    """The reason to block, or an empty string."""
    if not env.get("MAESTRI_TERMINAL_ID"):
        return ""
    role = env.get("ZE_ROLE", "").strip().lower()
    tool = payload.get("tool_name", "")
    if tool == "AskUserQuestion":
        if role and role != "maestro":
            return f"Only the Maestro asks the user (ZE_ROLE={role}). Batch your questions to the Maestro with maestri ask."
        return ""
    if tool not in ("Edit", "Write", "MultiEdit"):
        return ""
    raw = (payload.get("tool_input") or {}).get("file_path", "")
    if not raw:
        return ""
    path = Path(raw)
    if role == "review" and not in_scratchpad(path):
        return "Reviewers are read-only: write findings to a file in your scratchpad, not into the repository."
    root = toplevel(payload.get("cwd", ""))
    if root is None:
        return ""
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return ""
    posix = rel.as_posix()
    if posix.startswith((".process/receipts/", ".process/reviews/")):
        return "Receipts and review records are written by make process-ready / process-review-*, never by hand."
    if (
        posix.startswith("specs/arch/")
        and not path.exists()
        and role not in ("", "architect", "maestro")
    ):
        return "New files under specs/arch/ are for the architect or Maestro; do not leave working notes there."
    lane = root / ".process" / "lane.json"
    if lane.exists() and not in_scratchpad(path) and not posix.startswith(".process/"):
        owns = json.loads(lane.read_text()).get("owns", [])
        if not any(
            fnmatch.fnmatch(posix, g)
            or posix.startswith(g.rstrip("*").rstrip("/") + "/")
            for g in owns
        ):
            return f"{posix} is outside lane {json.loads(lane.read_text()).get('lane')}'s files; ask the lead to change shared files."
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    reason = decide(payload, dict(os.environ))
    if reason:
        print(f"BLOCKED by Ze process guard: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
