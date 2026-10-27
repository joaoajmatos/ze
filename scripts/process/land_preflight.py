#!/usr/bin/env python3
"""Refuse to land a floor that is not ready. Run before `maestri floor land`.

Checks (each failure is one line; exit 1 if any):
  1. the floor shares history with main and merges into it without conflicts
  2. no untracked files in the floor or in Ground that .git/info/exclude does not cover
  3. phase status is in sync (check_phase_status)
  4. no new files under specs/arch/ (no working notes there)
  5. a green gate receipt for the floor HEAD covers every gate the diff needs
  6. APPROVE review records chain from the merge base to HEAD
On success it archives the floor's and its lanes' review records and receipts to Ground's
journal/metrics/<branch>/ (metrics.py reads them), since landing deletes the floor.

Usage: land_preflight.py [--floor PATH] [--into main] [--dry-run]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import check_phase_status  # noqa: E402
import ready  # noqa: E402

CHECKS = [
    "history and merge conflicts",
    "untracked files in floor and Ground",
    "phase status sync",
    "no new specs/arch files",
    "gate receipt for HEAD",
    "review chain base..HEAD",
]


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )


def rev(repo: Path, ref: str) -> str:
    p = git(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
    return p.stdout.strip() if p.returncode == 0 else ""


def ground_of(floor: Path) -> Path:
    common = Path(
        git(
            floor, "rev-parse", "--path-format=absolute", "--git-common-dir"
        ).stdout.strip()
    )
    return common.parent


def check_history(floor: Path, into: str) -> list[str]:
    base = git(floor, "merge-base", "HEAD", into)
    if base.returncode != 0:
        return [f"history: HEAD shares no history with {into}"]
    merge = git(floor, "merge-tree", "--write-tree", "--name-only", into, "HEAD")
    if merge.returncode != 0:
        files = [
            line
            for line in merge.stdout.splitlines()[1:]
            if line and not line.startswith(("CONFLICT", "Auto-merging"))
        ]
        return [
            f"history: merging {into} into the floor conflicts ({', '.join(files[:5]) or 'see git merge-tree'}); merge {into} into the floor first"
        ]
    return []


def check_untracked(floor: Path, ground: Path) -> list[str]:
    errs = []
    for label, repo in (("floor", floor), ("Ground", ground)):
        out = git(
            repo, "status", "--porcelain", "--untracked-files=all"
        ).stdout.splitlines()
        untracked = [line[3:] for line in out if line.startswith("??")]
        if untracked:
            errs.append(
                f"untracked in {label}: {', '.join(untracked[:6])}{' ...' if len(untracked) > 6 else ''} (commit, delete, or add to .git/info/exclude)"
            )
    return errs


def check_phase(floor: Path) -> list[str]:
    cwd = Path.cwd()
    try:
        os.chdir(floor)
        agents, readme = (
            Path("AGENTS.md").read_text(),
            Path("specs/README.md").read_text(),
        )
        dirs = [
            d
            for d in sorted(Path("specs/phases").glob("*/"))
            if d.name[:3].isdigit()
            and int(d.name[:3]) >= check_phase_status.FIRST_CHECKED_PHASE
        ]
        return [e for d in dirs for e in check_phase_status.check(d, agents, readme)]
    finally:
        os.chdir(cwd)


def check_arch(floor: Path, base: str) -> list[str]:
    added = git(
        floor,
        "diff",
        "--name-only",
        "--diff-filter=A",
        f"{base}..HEAD",
        "--",
        "specs/arch/",
    ).stdout.split()
    return [f"new file under specs/arch/: {f}" for f in added]


def lane_checkouts(floor: Path, branch: str) -> list[Path]:
    """Worktrees of the floor's lanes (branches '<phase>-lane-*'), whose review records die with them."""
    phase = branch.split("-", 1)[0]
    paths, current = [], None
    for line in git(floor, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            current = Path(line[len("worktree ") :])
        elif line.startswith("branch refs/heads/") and current:
            if line[len("branch refs/heads/") :].startswith(f"{phase}-lane-"):
                paths.append(current)
    return paths


def archive_records(floor: Path, ground: Path) -> Path:
    """Copy review records, gate receipts and the agents' state files (those naming the branch) to Ground's
    journal/metrics/<branch>/ before landing deletes the floor."""
    branch = git(floor, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    dest = ground / "journal" / "metrics" / branch
    for repo in [floor, *lane_checkouts(floor, branch)]:
        for kind in ("reviews", "receipts"):
            src = repo / ".process" / kind
            if not src.is_dir():
                continue
            out = dest / kind
            out.mkdir(parents=True, exist_ok=True)
            for f in src.glob("*.json"):
                (out / f.name).write_text(f.read_text())
        for f in (repo / "journal" / "state").glob("*.md"):
            text = f.read_text()
            if branch in text:
                (dest / "state").mkdir(parents=True, exist_ok=True)
                (dest / "state" / f.name).write_text(text)
    return dest


def check_receipt(floor: Path, base: str, head: str) -> list[str]:
    path = floor / ".process" / "receipts" / f"{head}.json"
    if not path.exists():
        return [f"no gate receipt for HEAD {head[:8]} (run make process-ready)"]
    data = json.loads(path.read_text())
    errs = []
    if data.get("dirty_files"):
        errs.append(
            f"receipt {head[:8]} was taken with {data['dirty_files']} uncommitted file(s)"
        )
    failed = [g["gate"] for g in data.get("gates", []) if g["rc"] != 0]
    if failed:
        errs.append(f"receipt {head[:8]} has failing gates: {', '.join(failed)}")
    if data.get("ok") is False:
        errs.append(f"receipt {head[:8]} recorded a failed check (see its checks list)")
    changed = git(floor, "diff", "--name-only", f"{base}..HEAD").stdout.split()
    targets = ready.test_targets((floor / "Makefile").read_text())
    missing = [
        g
        for g in ready.select_gates(changed, targets)
        if g not in {x["gate"] for x in data.get("gates", [])}
    ]
    if missing:
        errs.append(
            f"receipt {head[:8]} lacks gates the diff needs: {', '.join(missing)}"
        )
    return errs


def review_records(floor: Path) -> list[dict]:
    return [
        json.loads(p.read_text())
        for p in sorted((floor / ".process" / "reviews").glob("*.json"))
    ]


def check_reviews(floor: Path, base: str, head: str) -> list[str]:
    approved = {}
    for record in review_records(floor):
        if record.get("verdict") == "APPROVE":
            start, end = rev(floor, record["from"]), rev(floor, record["to"])
            if start and end:
                approved.setdefault(start, []).append(end)
    cur = base
    while cur != head:
        nxt = [e for e in approved.get(cur, []) if e != cur]
        if not nxt:
            return [
                f"no APPROVE review record continues from {cur[:8]} (review chain must reach {head[:8]})"
            ]
        cur = max(
            nxt,
            key=lambda e: (
                git(floor, "rev-list", "--count", f"{cur}..{e}").stdout.strip().zfill(8)
            ),
        )
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", default=".")
    ap.add_argument("--into", default="main")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    floor = Path(args.floor).resolve()
    if args.dry_run:
        print(f"land preflight for {floor} into {args.into}:")
        print("\n".join(f"  {i}. {c}" for i, c in enumerate(CHECKS, 1)))
        return 0
    head, base = (
        rev(floor, "HEAD"),
        git(floor, "merge-base", "HEAD", args.into).stdout.strip(),
    )
    errs = (
        check_history(floor, args.into)
        + check_untracked(floor, ground_of(floor))
        + check_phase(floor)
    )
    if base:
        errs += (
            check_arch(floor, base)
            + check_receipt(floor, base, head)
            + check_reviews(floor, base, head)
        )
    if errs:
        print("\n".join(errs))
        return 1
    print(
        f"land preflight: ok (records archived to {archive_records(floor, ground_of(floor))})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
