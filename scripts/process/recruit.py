#!/usr/bin/env python3
"""Recruit an agent with the right role and tier, and make sure the brief arrived.

Usage: recruit.py <name> <role> <tier> <floor> <brief-file> [--note "<Floor> Handoffs"] [--dry-run]
  role/tier rules come from roles.toml; ZE_ROLE is set on the agent's command.
  Waits for the TUI, sends the brief with a "reply ready" ping, retries once with recruit --replace.
Tunables (tests): ZE_RECRUIT_BOOT_SECS (60), ZE_RECRUIT_REPLY_SECS (120), ZE_RECRUIT_POLL_SECS (2).
"""

import argparse
import os
import sys
import time
import tomllib
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import brief_lint  # noqa: E402
import handoff  # noqa: E402

PING = "\n\nReply with one line 'ready' first, then work."


def load_roles(path: Path = HERE / "roles.toml") -> dict:
    return tomllib.loads(path.read_text())


def command_for(config: dict, role: str, tier: str) -> tuple[str, str]:
    """The agent command and the Maestri role name, or SystemExit with the rule that was broken."""
    roles = config["roles"]
    if role not in roles:
        sys.exit(f"unknown role {role!r}; known: {', '.join(roles)}")
    if tier not in config["tiers"]:
        sys.exit(f"unknown tier {tier!r}; known: {', '.join(config['tiers'])}")
    if tier not in roles[role]["allowed"]:
        sys.exit(
            f"role {role} may not run on {tier}; allowed: {', '.join(roles[role]['allowed'])} (roles.toml)"
        )
    return f"ZE_ROLE={role} {config['tiers'][tier]}", roles[role]["maestri_role"]


def wait_for_tui(name: str, markers: list[str], seconds: float, poll: float) -> bool:
    deadline = time.monotonic() + seconds
    while True:
        out = handoff.maestri("check", name).stdout
        if any(m in out for m in markers):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll)


def stuck_in_input(screen: str, brief: str) -> bool:
    """The brief sits in the input box (under the prompt) and the agent has not answered (no reply marker)."""
    return brief.strip()[:40] in screen and "\u23fa" not in screen


def send_brief(name: str, brief: str, seconds: float, poll: float = 2.0) -> bool:
    reply = handoff.maestri("ask", name, brief + PING, timeout=seconds)
    if reply.returncode == 0 and "ready" in reply.stdout.lower():
        return True
    if not stuck_in_input(handoff.maestri("check", name).stdout, brief):
        return False
    handoff.maestri("ask", name, "--raw", "\r")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        screen = handoff.maestri("check", name).stdout
        if "\u23fa" in screen:
            return True
        time.sleep(poll)
    return False


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("role")
    ap.add_argument("tier")
    ap.add_argument("floor")
    ap.add_argument("brief")
    ap.add_argument("--note", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    config = load_roles()
    command, maestri_role = command_for(config, args.role, args.tier)
    brief = Path(args.brief).read_text()
    missing = brief_lint.lint(brief)
    if missing:
        print("brief is missing:\n  - " + "\n  - ".join(missing), file=sys.stderr)
        return 1
    recruit = [
        "recruit",
        args.name,
        "--role",
        maestri_role,
        "--floor",
        args.floor,
        "--command",
        command,
    ]
    if args.dry_run:
        print(f"{handoff.cli()} {' '.join(recruit)}")
        print(
            f"then wait for the TUI, send {args.brief} with a ready ping, retry once with --replace"
        )
        return 0

    boot = float(os.environ.get("ZE_RECRUIT_BOOT_SECS", 60))
    reply = float(os.environ.get("ZE_RECRUIT_REPLY_SECS", 120))
    poll = float(os.environ.get("ZE_RECRUIT_POLL_SECS", 2))
    if handoff.maestri(*recruit).returncode != 0:
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
            handoff.maestri("recruit", args.name, "--replace", args.name)
    handoff.append_handoff(
        Path.cwd(), args.note, f"ALERT: {args.name} never confirmed its brief"
    )
    print(
        f"{args.name}: brief not confirmed after one --replace; check the terminal by hand",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
