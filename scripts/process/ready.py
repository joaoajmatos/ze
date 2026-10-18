#!/usr/bin/env python3
"""make process-ready: run the gates the diff needs, run the hard checks, write one receipt for HEAD.

Hard checks (exit 1): every selected gate at rc 0, check_query_errors on changed query hooks.
Advisory (printed, never fail): old-route literals, docs touched, a portal screenshot for web changes.

Usage: ready.py [--base REF] [--portal-shot PATH] [--set-review FLOOR] [--dry-run] [--gate TARGET ...]
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
WEB_PREFIXES = ("apps/ze-web/", "packages/ze-ui/", "packages/ze-client/")
LAND_GATES = ["lint", "test-py", "test-web", "typecheck-web", "lint-web"]
WEB_GATES = ["typecheck-web", "lint-web", "test-web"]
BEHAVIOR = re.compile(
    r"(/api/|rest\.py|routes?\.py|@tool|config\.yaml|^Makefile$|pyproject\.toml)"
)
DOC = re.compile(r"(^|/)(README\.md|AGENTS\.md)$|^docs/")
DOCS_NONE = re.compile(r"^Docs: none \(.+\)", re.M)


def run(*cmd: str, check: bool = True) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if check and p.returncode:
        sys.exit(f"process-ready: {' '.join(cmd)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def test_targets(makefile: str) -> dict[str, str]:
    """Map each pytest path to its make target by reading the Makefile, so the map cannot go stale."""
    pairs = re.findall(
        r"^((?:test[\w-]*[ ]?)+):\n\t.*?pytest_pkg,([^)\s]+)\)", makefile, re.M
    )
    return {path.removesuffix("/tests"): names.split()[-1] for names, path in pairs}


def select_gates(changed: list[str], targets: dict[str, str]) -> list[str]:
    gates: list[str] = []
    py = [f for f in changed if f.endswith(".py")]
    if py:
        gates.append("lint")
    for path, target in sorted(targets.items(), key=lambda kv: -len(kv[0])):
        if any(f.startswith(path + "/") for f in py) and target not in gates:
            gates.append(target)
    for f in py:
        if f.startswith("scripts/") and "test-scripts" not in gates:
            gates.append("test-scripts")
    if any(f.startswith(WEB_PREFIXES) for f in changed):
        gates += [g for g in WEB_GATES if g not in gates]
    return gates


def old_route_hits(web_files: list[str]) -> list[str]:
    places = Path("apps/ze-web/src/shared/config/places.ts")
    if not places.exists():
        return []
    sources = re.findall(r'from: "(/[^":]*)"', places.read_text())
    hits = []
    for name in web_files:
        path = Path(name)
        if (
            path == places
            or ".test." in path.name
            or not path.exists()
            or path.suffix not in (".ts", ".tsx")
        ):
            continue
        text = path.read_text()
        hits += [
            f"{name}: literal {s!r} is an old route"
            for s in sources
            if re.search(rf"""["'`]{re.escape(s)}["'`]""", text)
        ]
    return hits


def docs_advisory(changed: list[str], base: str) -> list[str]:
    behavior = [
        f
        for f in changed
        if BEHAVIOR.search(f) and not f.startswith(("scripts/tests", "specs/"))
    ]
    if not behavior or any(DOC.search(f) for f in changed):
        return []
    if DOCS_NONE.search(run("git", "log", f"{base}..HEAD", "--format=%B", check=False)):
        return []
    return [
        f"docs: behavior paths changed ({behavior[0]} ...) with no public doc touched; add docs or a 'Docs: none (reason)' trailer"
    ]


def changed_files(base: str) -> list[str]:
    """Files changed since base, including new files that are not committed yet."""
    tracked = run("git", "diff", "--name-only", base).splitlines()
    untracked = run("git", "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked) | set(untracked))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="")
    ap.add_argument("--portal-shot", default="")
    ap.add_argument("--set-review", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--profile",
        choices=["diff", "land"],
        default="diff",
        help="land runs every gate, not only the diff's",
    )
    ap.add_argument(
        "--gate", action="append", default=[], help="extra make target to include"
    )
    args = ap.parse_args()

    root = Path(run("git", "rev-parse", "--show-toplevel"))
    os.chdir(root)
    base = args.base or run("git", "merge-base", "HEAD", "main")
    changed = changed_files(base)
    if args.profile == "land":
        gates = list(LAND_GATES)
    else:
        gates = select_gates(changed, test_targets(Path("Makefile").read_text()))
    gates += [g for g in args.gate if g not in gates]
    web = [f for f in changed if f.startswith(WEB_PREFIXES)]
    sha = run("git", "rev-parse", "HEAD")
    print(f"base {base[:8]}  head {sha[:8]}  {len(changed)} changed file(s)")
    print("gates:", " ".join(gates) or "(none)")
    if args.dry_run:
        return 0

    receipt = root / ".process" / "receipts" / f"{sha}.json"
    rc = 0
    if gates:
        rc = subprocess.run([str(HERE / "gates.sh"), "-", *gates]).returncode
    data = (
        json.loads(receipt.read_text())
        if receipt.exists()
        else {"sha": sha, "gates": []}
    )
    py = sys.executable

    checks = []
    hooks = [f for f in web if re.search(r"entities/[^/]+/api/use\w+Query\.tsx?$", f)]
    for name, cmd in [
        ("query_errors", [py, str(HERE / "check_query_errors.py"), *hooks]),
    ]:
        p = subprocess.run(cmd, capture_output=True, text=True)
        print(p.stdout.strip() or p.stderr.strip())
        checks.append({"check": name, "rc": p.returncode, "advisory": False})
        rc = rc or p.returncode

    advice = old_route_hits(web) + docs_advisory(changed, base)
    if web and not args.portal_shot:
        advice.append(
            "portal: web change with no --portal-shot <path>; verify in your Maestri portal (ze-web-verify)"
        )
    if args.portal_shot and not Path(args.portal_shot).exists():
        advice.append(f"portal: --portal-shot {args.portal_shot} does not exist")
    for line in advice:
        print("advisory:", line)

    data.update(
        checks=checks, advisory=advice, portal_shot=args.portal_shot or None, ok=rc == 0
    )
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(data, indent=1) + "\n")
    print(f"process-ready: {'ok' if rc == 0 else 'FAILED'}  receipt {receipt}")

    if rc == 0 and args.set_review:
        cli = os.environ.get("MAESTRI_CLI") or "maestri"
        rc = subprocess.run(
            [cli, "floor", "status", args.set_review, "--state", "review"]
        ).returncode
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
