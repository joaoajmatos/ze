#!/usr/bin/env python3
"""Review requests and verdicts as files, so neither can be lost in chat.

Usage:
  review.py request <a..b> <reviewer> [--requester NAME (default $ZE_AGENT, else "Claude Code")] [--note N] [--wait SECS] [--repo PATH]
  review.py verdict <a..b> APPROVE|CHANGES [--findings FILE] [--note N] [--repo PATH]
Records live in <repo>/.process/reviews/<a8>..<b8>.json. A request must start where the last
request or verdict ended (delta-only review), or at the merge base with main for the first one.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import handoff  # noqa: E402

VERDICTS = ("APPROVE", "CHANGES")


def not_connected(sent: subprocess.CompletedProcess) -> bool:
    """`maestri ask` reaches connected agents only; to anyone else it fails with "not found"."""
    return sent.returncode == 1 and "not found" in sent.stderr


def connect_hint(a: str, b: str) -> str:
    return f'{a} is not connected to {b}; ask the Maestro to run: maestri connect "{a}" "{b}" --agent, then run this again'


def git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def resolve(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")


def reviews_dir(repo: Path) -> Path:
    return repo / ".process" / "reviews"


def records(repo: Path) -> list[dict]:
    found = [json.loads(p.read_text()) for p in reviews_dir(repo).glob("*.json")]
    return sorted(found, key=lambda r: r["at"])


def record_path(repo: Path, start: str, end: str) -> Path:
    return reviews_dir(repo) / f"{start[:8]}..{end[:8]}.json"


def parse_range(repo: Path, text: str) -> tuple[str, str]:
    if ".." not in text:
        sys.exit(f"range must look like a..b, got {text!r}")
    left, right = text.split("..", 1)
    start, end = resolve(repo, left), resolve(repo, right)
    if not start or not end:
        sys.exit(f"range {text!r}: a ref does not exist in {repo}")
    if subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", start, end]
    ).returncode:
        sys.exit(f"range {text!r}: {left} is not an ancestor of {right}")
    if start == end:
        sys.exit(f"range {text!r} is empty")
    return start, end


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", a, b],
            capture_output=True,
        ).returncode
        == 0
    )


def approved_end(repo: Path, base: str, into: str = "main") -> str:
    """Where the APPROVE records end. A chain may start at the merge base or at any approved range start
    already on `into` (merging main moves the merge base; main's commits are reviewed there). Only ranges
    whose end is in HEAD count, so a lane rebased after approval does not shadow the commit in the branch."""
    edges: dict[str, list[str]] = {}
    for r in records(repo):
        if r.get("verdict") == "APPROVE" and is_ancestor(repo, r["to"], "HEAD"):
            edges.setdefault(r["from"], []).append(r["to"])
    starts = {base} | {s for s in edges if is_ancestor(repo, s, into)}
    best = base
    for start in starts:
        cur = start
        while edges.get(cur):
            cur = max(
                edges[cur],
                key=lambda e: int(git(repo, "rev-list", "--count", f"{cur}..{e}") or 0),
            )
        if int(git(repo, "rev-list", "--count", cur) or 0) > int(
            git(repo, "rev-list", "--count", best) or 0
        ):
            best = cur
    return best


def contiguity_problem(repo: Path, start: str) -> str:
    """A request starts where approval ended (a re-review after CHANGES covers the whole un-approved range)
    or where a request still in flight ends (parallel stories)."""
    base = git(repo, "merge-base", "HEAD", "main")
    if not base:
        return ""
    allowed = {approved_end(repo, base)}
    allowed |= {r["to"] for r in records(repo) if r.get("state") == "requested"}
    if start in allowed:
        return ""
    where = ", ".join(sorted(a[:8] for a in allowed))
    return f"range must start at {where}: the end of the last APPROVE, or of a request in flight (delta-only review)"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def request(args) -> int:
    repo = Path(args.repo).resolve()
    start, end = parse_range(repo, args.range)
    problem = contiguity_problem(repo, start)
    if problem:
        print(f"review request refused: {problem}", file=sys.stderr)
        return 1
    path = record_path(repo, start, end)
    record = {
        "from": start,
        "to": end,
        "reviewer": args.reviewer,
        "requester": args.requester,
        "state": "requested",
        "at": now(),
    }
    reviews_dir(repo).mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1) + "\n")

    before = handoff.maestri("check", args.reviewer).stdout
    token = f"rq{uuid.uuid4().hex[:6]}"
    text = (
        f"[{token}] Review {start[:8]}..{end[:8]} in {repo} (read-only). When done run, from that directory: "
        f"make process-review-verdict RANGE={start[:8]}..{end[:8]} VERDICT=APPROVE|CHANGES FINDINGS=<file>. "
        "That records the verdict and delivers it; do not report it by chat alone."
    )
    sent = handoff.maestri("ask", args.reviewer, text, timeout=15)
    if not_connected(sent):
        print(
            f"request recorded, not delivered: {connect_hint(args.requester, args.reviewer)}",
            file=sys.stderr,
        )
        return 1
    handoff.append_handoff(
        repo,
        args.note,
        f"TO {args.reviewer}: review requested {start[:8]}..{end[:8]} ({path.name})",
    )
    started = _started(args.reviewer, before, token, args.wait)
    if not started:
        print(
            f"ALERT: {args.reviewer} still has the request unsubmitted {args.wait:.0f}s after it was sent; check the terminal",
            file=sys.stderr,
        )
        handoff.maestri(
            "ask",
            args.requester,
            f"ALERT: reviewer {args.reviewer} never started {start[:8]}..{end[:8]}",
            timeout=15,
        )
        return 1
    print(f"review requested and started: {path}")
    return 0


REPLY_MARK = "\u23fa"


BUSY_MARK = "esc to interrupt"


def _working(screen: str, before: str) -> bool:
    """A new reply marker, or the agent is busy (the ask queues behind its current work)."""
    return screen.count(REPLY_MARK) > before.count(REPLY_MARK) or BUSY_MARK in screen


def _started(reviewer: str, before: str, token: str, wait: float) -> bool:
    """False only when the request is stuck: the agent is idle and the text still sits under the prompt.
    One Enter is tried first. `token` is the short unique tag at the start of the ask."""
    time.sleep(wait)
    after = handoff.maestri("check", reviewer).stdout
    if _working(after, before):
        return True
    if token not in after:
        return (
            True  # idle with nothing in the input box: the ask was taken and answered
        )
    handoff.maestri("ask", reviewer, "--raw", "\r", timeout=15)
    time.sleep(min(wait, 15))
    return _working(handoff.maestri("check", reviewer).stdout, before)


def verdict(args) -> int:
    repo = Path(args.repo).resolve()
    start, end = parse_range(repo, args.range)
    path = record_path(repo, start, end)
    if not path.exists():
        print(
            f"no review request {path.name} in {repo}; ask the requester to run make process-review-request",
            file=sys.stderr,
        )
        return 1
    findings = Path(args.findings).read_text() if args.findings else ""
    if args.verdict == "CHANGES" and not findings.strip():
        print(
            "a CHANGES verdict needs FINDINGS=<file> with the findings", file=sys.stderr
        )
        return 1
    record = json.loads(path.read_text())
    record.update(
        state="delivered", verdict=args.verdict, findings=findings, delivered_at=now()
    )
    path.write_text(json.dumps(record, indent=1) + "\n")
    summary = f"{args.verdict} for {start[:8]}..{end[:8]} (record {path})"
    message = summary + (f"\n\n{findings[:6000]}" if findings else "")
    sent = handoff.maestri("ask", record["requester"], message, timeout=30)
    if not_connected(sent):
        print(
            f"verdict recorded, not delivered: {connect_hint(record['reviewer'], record['requester'])}",
            file=sys.stderr,
        )
        return 1
    handoff.append_handoff(
        repo, args.note, f"TO {record['requester']}: review verdict {summary}"
    )
    if sent.returncode not in (0, 124):
        print(
            f"verdict recorded but the ask to {record['requester']} failed (rc {sent.returncode}); resend by hand",
            file=sys.stderr,
        )
        return 1
    print(f"verdict delivered: {summary}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    req = sub.add_parser("request")
    req.add_argument("range")
    req.add_argument("reviewer")
    # The verdict goes back to whoever asked: a recruited agent carries its own name in ZE_AGENT.
    req.add_argument("--requester", default=os.environ.get("ZE_AGENT") or "Claude Code")
    req.add_argument("--wait", type=float, default=60)
    ver = sub.add_parser("verdict")
    ver.add_argument("range")
    ver.add_argument("verdict", choices=VERDICTS)
    ver.add_argument("--findings", default="")
    for p in (req, ver):
        p.add_argument("--note", default="")
        p.add_argument(
            "--repo", default=git(Path.cwd(), "rev-parse", "--show-toplevel") or "."
        )
    args = ap.parse_args(argv)
    return request(args) if args.cmd == "request" else verdict(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
