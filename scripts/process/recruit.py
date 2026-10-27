#!/usr/bin/env python3
"""Recruit an agent with the right role and tier, and make sure the brief arrived.

Usage: recruit.py <name> <role> <tier> <floor> <brief-file> [--note "<Floor> Handoffs"] [--connect AGENT ...] [--dry-run]
  role/tier rules come from roles.toml; ZE_ROLE is set on the agent's command.
  --connect wires the new agent to each named agent (its reviewer, its lead), since `maestri ask`
  reaches connected agents only. Waits for the TUI, sends the brief without waiting for the agent's turn, counts it delivered once the agent says ready or is busy, presses Enter once on a brief stuck in the input box, and starts over once only if nothing arrived.
Tunables (tests): ZE_RECRUIT_BOOT_SECS (60), ZE_RECRUIT_REPLY_SECS (90: the brief counts as delivered once the agent is busy), ZE_RECRUIT_POLL_SECS (2).
"""

import argparse
import os
import re
import shlex
import sys
import time
import tomllib
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import brief_lint  # noqa: E402
import handoff  # noqa: E402

PING = "\n\nReply with one line 'ready' first, then work."


def load_roles(path: Path = HERE / "roles.toml") -> dict:
    return tomllib.loads(path.read_text())


def command_for(config: dict, role: str, tier: str, name: str = "") -> tuple[str, str]:
    """The agent command and the Maestri role name (empty for the Maestro), or SystemExit with the rule that was broken."""
    roles = config["roles"]
    if role not in roles:
        sys.exit(f"unknown role {role!r}; known: {', '.join(roles)}")
    if tier not in config["tiers"]:
        sys.exit(f"unknown tier {tier!r}; known: {', '.join(config['tiers'])}")
    if tier not in roles[role]["allowed"]:
        sys.exit(
            f"role {role} may not run on {tier}; allowed: {', '.join(roles[role]['allowed'])} (roles.toml)"
        )
    env = f"ZE_ROLE={role}" + (f" ZE_AGENT={shlex.quote(name)}" if name else "")
    return f"{env} {config['tiers'][tier]}", roles[role].get("maestri_role", "")


def wait_for_tui(name: str, markers: list[str], seconds: float, poll: float) -> bool:
    deadline = time.monotonic() + seconds
    while True:
        out = handoff.maestri("check", name).stdout
        if any(m in out for m in markers):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll)


READY_LINE = re.compile(r"^\s*(\u23fa\s*)?ready\.?\s*$", re.I | re.M)


def said_ready(screen: str) -> bool:
    """A line that is exactly 'ready': the echoed ping ('Reply with one line ready') does not count."""
    return READY_LINE.search(screen) is not None


REPLY_MARK = "\u23fa"
BUSY_MARK = "esc to interrupt"
SEND_SECS = 15


def delivered(screen: str, before: str) -> bool:
    """The agent answered 'ready', printed a new reply, or is busy working on the brief."""
    return (
        said_ready(screen)
        or screen.count(REPLY_MARK) > before.count(REPLY_MARK)
        or BUSY_MARK in screen
    )


def transcripts_root() -> Path:
    return Path(
        os.environ.get("ZE_TRANSCRIPTS_DIR") or Path.home() / ".claude" / "projects"
    )


def in_transcript(token: str, since: float) -> bool:
    """The agent's Claude Code session log holds the token: the brief was submitted, whatever the screen shows."""
    for log in transcripts_root().glob("*/*.jsonl"):
        try:
            if log.stat().st_mtime >= since and token in log.read_text(errors="ignore"):
                return True
        except OSError:
            continue
    return False


def send_brief(name: str, brief: str, seconds: float, poll: float = 2.0) -> bool:
    """Send without waiting for the agent's turn to end (`ask` blocks until it goes idle, and the agent
    keeps working after 'ready'). The brief carries a short token: finding it in the agent's session
    transcript proves delivery; the screen is the fallback, and a token still under the prompt (unsent,
    even when the TUI wraps it) gets one Enter."""
    before = handoff.maestri("check", name).stdout
    token = f"[bf{uuid.uuid4().hex[:6]}]"
    sent_at = time.time() - 1
    reply = handoff.maestri("ask", name, f"{token} {brief}{PING}", timeout=SEND_SECS)
    if said_ready(reply.stdout) or in_transcript(token, sent_at):
        return True
    deadline, nudged = time.monotonic() + seconds, False
    while time.monotonic() < deadline:
        screen = handoff.maestri("check", name).stdout
        if in_transcript(token, sent_at) or delivered(screen, before):
            return True
        if token in screen and not nudged:
            handoff.maestri("ask", name, "--raw", "\r", timeout=SEND_SECS)
            nudged = True
        time.sleep(poll)
    return False


def connect(name: str, others: list[str]) -> list[str]:
    """Wire `name` to each of `others`; the names that failed."""
    return [
        other
        for other in others
        if handoff.maestri("connect", name, other, "--agent").returncode != 0
    ]


def recruit_and_connect(recruit: list[str], name: str, others: list[str]) -> bool:
    if handoff.maestri(*recruit).returncode != 0:
        return False
    failed = connect(name, others)
    if failed:
        print(
            f"{name}: could not connect to {', '.join(failed)}; run maestri connect by hand",
            file=sys.stderr,
        )
    return True


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("role")
    ap.add_argument("tier")
    ap.add_argument("floor")
    ap.add_argument("brief")
    ap.add_argument("--note", default="")
    ap.add_argument("--connect", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    config = load_roles()
    command, maestri_role = command_for(config, args.role, args.tier, args.name)
    brief = Path(args.brief).read_text()
    missing = brief_lint.lint(brief)
    if missing:
        print("brief is missing:\n  - " + "\n  - ".join(missing), file=sys.stderr)
        return 1
    recruit = ["recruit", args.name]
    if maestri_role:
        recruit += ["--role", maestri_role]
    recruit += ["--floor", args.floor, "--command", command]
    if args.dry_run:
        print(f"{handoff.cli()} {' '.join(recruit)}")
        for other in args.connect:
            print(f'{handoff.cli()} connect "{args.name}" "{other}" --agent')
        print(
            f"then wait for the TUI, send {args.brief} with a ready ping, retry once (dismiss, then recruit again)"
        )
        return 0

    boot = float(os.environ.get("ZE_RECRUIT_BOOT_SECS", 60))
    reply = float(os.environ.get("ZE_RECRUIT_REPLY_SECS", 90))
    poll = float(os.environ.get("ZE_RECRUIT_POLL_SECS", 2))
    if not recruit_and_connect(recruit, args.name, args.connect):
        print("recruit failed", file=sys.stderr)
        return 1
    for attempt in (1, 2):
        if not wait_for_tui(args.name, config["ready_markers"], boot, poll):
            print(
                f"{args.name}: TUI not ready after {boot:.0f}s (attempt {attempt})",
                file=sys.stderr,
            )
        elif send_brief(args.name, brief, reply, poll):
            handoff.append_handoff(
                Path.cwd(),
                args.note,
                f"TO {args.name}: brief {Path(args.brief).name} delivered, agent replied ready",
            )
            print(f"{args.name}: brief delivered, agent ready")
            return 0
        else:
            print(
                f"{args.name}: no 'ready' reply within {reply:.0f}s (attempt {attempt})",
                file=sys.stderr,
            )
        if attempt == 1:
            # --replace keeps neither --role nor --command, so start over with the same arguments
            handoff.maestri("dismiss", args.name)
            if not recruit_and_connect(recruit, args.name, args.connect):
                print("recruit failed on the retry", file=sys.stderr)
                return 1
    handoff.append_handoff(
        Path.cwd(), args.note, f"ALERT: {args.name} never confirmed its brief"
    )
    print(
        f"{args.name}: brief not confirmed after one fresh recruit; check the terminal by hand",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
