#!/usr/bin/env python3
"""A plan's Lane Plan must be buildable by a crew: disjoint lanes, a lead, a model and reviewer per lane, every task tagged.

Usage: check_lane_plan.py [feature_dir ...]   (default: every phase whose plan.md has a Lane Plan)  exit 1 on a miss.
"""

import fnmatch
import re
import sys
from pathlib import Path

TASK = re.compile(r"^- \[[ xX]\] (T\d{3}[a-z]?)\b(.*)$", re.M)
PLACEHOLDER = re.compile(r"^\[.*\]$|^$|^-$")


def lane_section(plan: str) -> str | None:
    match = re.search(r"^## Lane Plan[^\n]*\n(.*?)(?=^## |\Z)", plan, re.S | re.M)
    return match.group(1) if match else None


def parse_lanes(section: str) -> dict[str, dict[str, str]]:
    lanes = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if (
            not line.strip().startswith("|")
            or len(cells) < 6
            or cells[0].lower() == "lane"
            or set(cells[0]) <= {"-", " "}
        ):
            continue
        lanes[cells[0].strip("`")] = {
            "model": cells[1],
            "owns": cells[2],
            "tasks": cells[3],
            "reviewer": cells[5],
        }
    return lanes


def owned_paths(owns: str) -> list[str]:
    ticked = re.findall(r"`([^`]+)`", owns)
    parts = ticked or [p.strip() for p in owns.split(",")]
    return [p for p in parts if " " not in p and ("/" in p or "." in p or "*" in p)]


def overlaps(a: str, b: str) -> bool:
    ra, rb = a.rstrip("/*"), b.rstrip("/*")
    return (
        fnmatch.fnmatch(a, b)
        or fnmatch.fnmatch(b, a)
        or ra == rb
        or ra.startswith(rb + "/")
        or rb.startswith(ra + "/")
    )


def check(feature: Path) -> list[str]:
    plan_file, tasks_file = feature / "plan.md", feature / "tasks.md"
    name = feature.name
    section = lane_section(plan_file.read_text()) if plan_file.exists() else None
    if section is None:
        return [f"{name}: plan.md has no '## Lane Plan' section"]
    lanes = parse_lanes(section)
    errs = []
    if "lead" not in lanes:
        errs.append(f"{name}: Lane Plan has no `lead` lane (the contract step)")
    for lane, row in lanes.items():
        if PLACEHOLDER.match(row["model"]):
            errs.append(f"{name}: lane {lane} has no model/role")
        if PLACEHOLDER.match(row["reviewer"]):
            errs.append(f"{name}: lane {lane} has no reviewer")
    names = list(lanes)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            for a in owned_paths(lanes[first]["owns"]):
                for b in owned_paths(lanes[second]["owns"]):
                    if overlaps(a, b):
                        errs.append(
                            f"{name}: lanes {first} and {second} both own {a} / {b}"
                        )
    if tasks_file.exists():
        for task_id, rest in TASK.findall(tasks_file.read_text()):
            tag = re.search(r"\[L:([\w-]+)\]", rest)
            if not tag:
                errs.append(f"{name}: {task_id} has no [L:x] lane tag")
                continue
            lane = tag.group(1)
            if lane not in lanes:
                errs.append(
                    f"{name}: {task_id} is tagged [L:{lane}], which the Lane Plan does not define"
                )
            elif (
                re.search(r"\bJR\b|haiku", lanes[lane]["model"], re.I)
                and "[ENG]" in rest
            ):
                errs.append(
                    f"{name}: {task_id} is tagged [ENG] but sits in JR lane {lane}"
                )
    return errs


def phases_with_lane_plan() -> list[Path]:
    return [
        d
        for d in sorted(Path("specs/phases").glob("*/"))
        if (d / "plan.md").exists()
        and lane_section((d / "plan.md").read_text()) is not None
    ]


def main(argv: list[str]) -> int:
    dirs = [Path(a) for a in argv] or phases_with_lane_plan()
    errs = [e for d in dirs for e in check(d)]
    print("\n".join(errs) or "lane plan: ok")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
