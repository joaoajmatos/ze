#!/usr/bin/env python3
"""Per-floor process metrics from the records land_preflight archives to journal/metrics/<branch>/.

Columns: reviews (verdicts recorded), changes (CHANGES verdicts), first-pass (share of review ranges
approved without a CHANGES round), advisor (calls logged under **Advisor** in the agents' state files),
followed (share of those calls whose advice was followed).

Usage: metrics.py [--root journal/metrics] [--json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

ADVISOR_LINE = re.compile(
    r"\b(proceed|change course|stop and escalate)\b.*\b(followed|overrode)\b", re.I
)


def review_stats(reviews: Path) -> dict:
    verdicts = []
    for f in reviews.glob("*.json"):
        try:
            verdicts.append(json.loads(f.read_text()).get("verdict"))
        except json.JSONDecodeError:
            continue
    done = [v for v in verdicts if v in ("APPROVE", "CHANGES")]
    approve, changes = done.count("APPROVE"), done.count("CHANGES")
    return {
        "reviews": len(done),
        "changes": changes,
        "first_pass": round(max(approve - changes, 0) / approve, 2)
        if approve
        else None,
    }


def advisor_lines(state_file: Path) -> list[str]:
    lines, inside = [], False
    for line in state_file.read_text().splitlines():
        if line.lstrip("#* ").lower().startswith("advisor"):
            inside = True
            continue
        if inside and (line.startswith("#") or line.startswith("**")):
            inside = False
        if inside and ADVISOR_LINE.search(line):
            lines.append(line)
    return lines


def floor_stats(floor_dir: Path) -> dict:
    stats = review_stats(floor_dir / "reviews")
    calls = [
        line
        for f in sorted((floor_dir / "state").glob("*.md"))
        for line in advisor_lines(f)
    ]
    followed = sum("followed" in c.lower() for c in calls)
    stats |= {
        "advisor": len(calls),
        "followed": round(followed / len(calls), 2) if calls else None,
    }
    return stats


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="journal/metrics")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root)
    rows = {d.name: floor_stats(d) for d in sorted(root.glob("*/")) if d.is_dir()}
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    if not rows:
        print(f"no archived floors under {root}")
        return 0
    fmt = "{:<34} {:>7} {:>7} {:>10} {:>7} {:>8}"
    print(
        fmt.format("floor", "reviews", "changes", "first-pass", "advisor", "followed")
    )
    for name, s in rows.items():
        print(
            fmt.format(
                name,
                s["reviews"],
                s["changes"],
                str(s["first_pass"]),
                s["advisor"],
                str(s["followed"]),
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
