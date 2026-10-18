#!/usr/bin/env python3
"""Trigger and behavior evals for the model-invoked Ze skills (skill-creator / skillopt method).

  skill_eval.py --check                         offline: validate every task file (free)
  skill_eval.py --dry-run [skill]               print the plan and how many claude runs it would cost (free)
  skill_eval.py --run <skill> --yes-spend-usage run on Claude subscription usage (never OpenRouter), in a throwaway worktree

Task files: scripts/process/skill_evals/<skill>.json
  {"skill": "...", "triggers": [{"query": "...", "should_trigger": true}, ...],
   "behaviors": [{"id": "...", "prompt": "...", "judges": [{"op": "tool_called", "tool": "Bash", "match": "regex"}, ...]}]}
Judges grade what the agent did (outcome ops), not what it wrote: tool_called, cmd_matches, not_cmd_matches.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EVALS = Path(__file__).parent / "skill_evals"
MODELS = ("haiku", "sonnet")
RUNS = 3
MIN_TRIGGERS = 20
PASS_BAR = 0.9


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def split(queries: list[dict]) -> tuple[list[dict], list[dict]]:
    """A stable 60/40 train/test split keyed on the query text."""
    train, test = [], []
    for q in queries:
        bucket = int(hashlib.sha256(q["query"].encode()).hexdigest(), 16) % 10
        (train if bucket < 6 else test).append(q)
    return train, test


def validate(task: dict) -> list[str]:
    errs = []
    triggers = task.get("triggers", [])
    if len(triggers) < MIN_TRIGGERS:
        errs.append(
            f"{task.get('skill')}: {len(triggers)} trigger queries, need {MIN_TRIGGERS}"
        )
    yes = sum(1 for t in triggers if t["should_trigger"])
    if yes != len(triggers) - yes:
        errs.append(
            f"{task.get('skill')}: {yes} should-trigger vs {len(triggers) - yes} near-miss; keep them equal"
        )
    if len({t["query"] for t in triggers}) != len(triggers):
        errs.append(f"{task.get('skill')}: duplicate trigger queries")
    if not task.get("behaviors"):
        errs.append(f"{task.get('skill')}: no behavior scenarios")
    for b in task.get("behaviors", []):
        for j in b["judges"]:
            if j["op"] not in ("tool_called", "cmd_matches", "not_cmd_matches"):
                errs.append(f"{b['id']}: unknown judge op {j['op']!r}")
    if not (
        EVALS.parent.parent.parent
        / ".claude"
        / "skills"
        / task.get("skill", "")
        / "SKILL.md"
    ).exists():
        errs.append(f"{task.get('skill')}: no such skill")
    return errs


def tool_calls(transcript: list[dict]) -> list[tuple[str, dict]]:
    """(tool name, input) for each tool_use in a claude stream-json transcript."""
    calls = []
    for event in transcript:
        for block in (event.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                calls.append((block["name"], block.get("input") or {}))
    return calls


def triggered(transcript: list[dict], skill: str) -> bool:
    return any(
        name == "Skill" and inp.get("skill", "").split(":")[-1] == skill
        for name, inp in tool_calls(transcript)
    )


def grade(transcript: list[dict], judges: list[dict]) -> list[tuple[str, bool]]:
    calls = tool_calls(transcript)
    commands = [inp.get("command", "") for name, inp in calls if name == "Bash"]
    results = []
    for j in judges:
        if j["op"] == "tool_called":
            ok = any(
                name == j["tool"] and re.search(j.get("match", ""), json.dumps(inp))
                for name, inp in calls
            )
        elif j["op"] == "cmd_matches":
            ok = any(re.search(j["match"], c) for c in commands)
        else:
            ok = not any(re.search(j["match"], c) for c in commands)
        results.append((f"{j['op']} {j.get('match', j.get('tool'))}", ok))
    return results


def accuracy(rows: list[tuple[bool, bool]]) -> float:
    return sum(want == got for want, got in rows) / len(rows) if rows else 0.0


def plan(task: dict) -> str:
    train, test = split(task["triggers"])
    runs = len(task["triggers"]) * RUNS * len(MODELS) + len(task["behaviors"]) * len(
        MODELS
    )
    return (
        f"{task['skill']}: {len(task['triggers'])} trigger queries ({len(train)} train / {len(test)} test) x {RUNS} runs x {len(MODELS)} models, "
        f"{len(task['behaviors'])} behavior scenarios = {runs} claude runs; pass bar {PASS_BAR} on the test split"
    )


def claude_run(prompt: str, model: str, cwd: Path) -> list[dict]:
    p = subprocess.run(
        [
            "claude",
            "-p",
            "--model",
            model,
            "--output-format",
            "stream-json",
            "--verbose",
            prompt,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return [json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]


def run(task: dict) -> int:
    train, test = split(task["triggers"])
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "tree"
        subprocess.run(
            ["git", "worktree", "add", "-q", "--detach", str(tree)], check=True
        )
        try:
            failed = False
            for model in MODELS:
                for label, subset in (("train", train), ("test", test)):
                    rows = [
                        (
                            q["should_trigger"],
                            triggered(
                                claude_run(q["query"], model, tree), task["skill"]
                            ),
                        )
                        for q in subset
                        for _ in range(RUNS)
                    ]
                    acc = accuracy(rows)
                    print(f"{task['skill']} {model} {label}: accuracy {acc:.2f}")
                    failed |= label == "test" and acc < PASS_BAR
                for b in task["behaviors"]:
                    results = grade(claude_run(b["prompt"], model, tree), b["judges"])
                    print(
                        f"{b['id']} {model}: "
                        + ", ".join(
                            f"{'ok' if ok else 'FAIL'} {name}" for name, ok in results
                        )
                    )
                    failed |= not all(ok for _, ok in results)
            return 1 if failed else 0
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(tree)], capture_output=True
            )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("skill", nargs="?")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--yes-spend-usage", action="store_true")
    args = ap.parse_args(argv)
    files = sorted(EVALS.glob("*.json"))
    if args.skill:
        files = [f for f in files if f.stem == args.skill]
    if not files:
        print("no task files", file=sys.stderr)
        return 1
    tasks = [load(f) for f in files]
    if args.check or args.dry_run:
        errs = [e for t in tasks for e in validate(t)]
        if args.dry_run:
            print("\n".join(plan(t) for t in tasks))
        print("\n".join(errs) or "skill evals: ok")
        return 1 if errs else 0
    if args.run:
        if not args.yes_spend_usage:
            print(
                "this spends Claude usage; pass --yes-spend-usage after the user agrees",
                file=sys.stderr,
            )
            return 2
        return max(run(t) for t in tasks)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
