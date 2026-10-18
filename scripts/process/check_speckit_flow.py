#!/usr/bin/env python3
"""Did the speckit flow leave its artifacts? Reads the files, not any journal.

  spec.md    has a '## Clarifications' section
  plan.md    has a '## Lane Plan' section
  tasks.md   every task line carries [L:x]
  complex phases (spec.md has '**Complexity**: complex') also need checklists/*.md and an analyze
  result: analysis.md, or an '## Analysis' section in plan.md or tasks.md

Usage: check_speckit_flow.py [feature_dir ...]   (default: every phase whose plan.md has a Lane Plan)  exit 1 on a miss.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import check_lane_plan  # noqa: E402

COMPLEX = re.compile(r"^\*\*Complexity\*?\*?:?\*?\*?:?\s*complex\b", re.I | re.M)


def has_heading(text: str, heading: str) -> bool:
    return re.search(rf"^##\s+{heading}\b", text, re.M | re.I) is not None


def check(feature: Path) -> list[str]:
    name = feature.name
    spec, plan, tasks = (feature / f for f in ("spec.md", "plan.md", "tasks.md"))
    errs = []
    spec_text = spec.read_text() if spec.exists() else ""
    if not spec.exists():
        errs.append(f"{name}: no spec.md")
    elif not has_heading(spec_text, "Clarifications"):
        errs.append(
            f"{name}: spec.md has no Clarifications section (run speckit-clarify)"
        )
    if not plan.exists():
        errs.append(f"{name}: no plan.md")
    elif check_lane_plan.lane_section(plan.read_text()) is None:
        errs.append(f"{name}: plan.md has no Lane Plan section")
    if not tasks.exists():
        errs.append(f"{name}: no tasks.md")
    else:
        untagged = [
            t
            for t, rest in check_lane_plan.TASK.findall(tasks.read_text())
            if not re.search(r"\[L:[\w-]+\]", rest)
        ]
        if untagged:
            errs.append(
                f"{name}: tasks without [L:x]: {', '.join(untagged[:6])}{' ...' if len(untagged) > 6 else ''}"
            )
    if COMPLEX.search(spec_text):
        if not [
            p for p in (feature / "checklists").glob("*.md") if p.read_text().strip()
        ]:
            errs.append(
                f"{name}: complex phase has no checklists/*.md (run speckit-checklist)"
            )
        analysed = (feature / "analysis.md").exists() or any(
            f.exists() and has_heading(f.read_text(), "Analysis") for f in (plan, tasks)
        )
        if not analysed:
            errs.append(
                f"{name}: complex phase has no analyze result (analysis.md or an '## Analysis' section)"
            )
    return errs


def main(argv: list[str]) -> int:
    dirs = [Path(a) for a in argv] or check_lane_plan.phases_with_lane_plan()
    errs = [e for d in dirs for e in check(d)]
    print("\n".join(errs) or "speckit flow: ok")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
