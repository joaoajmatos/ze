#!/usr/bin/env python3
"""A phase whose tasks are all ticked must read Implemented in spec.md, the AGENTS.md table and specs/README.md.

The reverse holds too: a spec marked Implemented may not have open tasks.
Usage: check_phase_status.py [feature_dir ...]   (default: phases numbered 160 and up)  exit 1 on drift.
"""

import re
import sys
from pathlib import Path

FIRST_CHECKED_PHASE = 160
TASK = re.compile(r"^- \[([ xX])\] T\d{3}[a-z]?\b", re.M)
SPEC_STATUS = re.compile(r"^\*\*Status:?\*\*:?\s*(.+)$", re.M)


def tasks_state(feature: Path) -> str:
    """'done' when every task is ticked, 'open' when any is not, '' without tasks."""
    tasks = feature / "tasks.md"
    marks = TASK.findall(tasks.read_text()) if tasks.exists() else []
    if not marks:
        return ""
    return "done" if all(m.lower() == "x" for m in marks) else "open"


def row_status(text: str, number: str, pattern: str) -> str | None:
    match = re.search(pattern.format(n=re.escape(number)), text, re.M)
    return match.group(1) if match else None


def check(feature: Path, agents: str, readme: str) -> list[str]:
    state = tasks_state(feature)
    spec = feature / "spec.md"
    if not state or not spec.exists():
        return []
    number = feature.name.split("-")[0].lstrip("0") or "0"
    found = SPEC_STATUS.search(spec.read_text())
    spec_done = bool(
        found and found.group(1).strip().lstrip("✅ ").lower().startswith("implemented")
    )
    agents_row = row_status(agents, number, r"^\| {n} \|.*\| (\S[^|]*?) \|\s*$")
    readme_row = row_status(readme, number, r"^\| {n} \| .*\| (.*?) \|\s*$")
    agents_done = bool(agents_row and agents_row.lower().startswith("implemented"))
    readme_done = bool(readme_row and "implemented" in readme_row.lower())
    errs = []
    if state == "done":
        if not spec_done:
            errs.append(
                f"{feature.name}: all tasks ticked but spec.md Status is not Implemented"
            )
        if agents_row is not None and not agents_done:
            errs.append(
                f"{feature.name}: all tasks ticked but the AGENTS.md row says {agents_row!r}"
            )
        if agents_row is None:
            errs.append(
                f"{feature.name}: all tasks ticked but AGENTS.md has no phase row for {number}"
            )
        if readme_row is not None and not readme_done:
            errs.append(
                f"{feature.name}: all tasks ticked but the specs/README.md row says {readme_row!r}"
            )
        if readme_row is None:
            errs.append(
                f"{feature.name}: all tasks ticked but specs/README.md has no row for {number}"
            )
    elif spec_done or agents_done:
        errs.append(f"{feature.name}: marked Implemented but tasks.md has open tasks")
    return errs


def main(argv: list[str]) -> int:
    dirs = [Path(a) for a in argv] or [
        d
        for d in sorted(Path("specs/phases").glob("*/"))
        if d.name[:3].isdigit() and int(d.name[:3]) >= FIRST_CHECKED_PHASE
    ]
    agents = Path("AGENTS.md").read_text()
    readme = Path("specs/README.md").read_text()
    errs = [e for d in dirs for e in check(d, agents, readme)]
    print("\n".join(errs) or "phase status: ok")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
