#!/usr/bin/env python3
"""PreToolUse(Bash) guard for Ze agents (Claude Code hook contract).

Exit 2 + stderr blocks the call; exit 0 with a permissionDecision JSON on stdout asks the user.
A no-op unless MAESTRI_TERMINAL_ID is set, so a person's own shell keeps working.
ZE_ROLE (maestro|architect|eng|jr|review|qa|docs) scopes the role rules; unset means unrestricted.
It catches mistakes, not adversaries: receipts and land preflight are the real gate.
"""

import json
import os
import re
import shlex
import sys

DENY, ASK, ALLOW = "deny", "ask", "allow"
SEPARATORS = {";", "&&", "||", "|", "&", "|&"}
WRAPPERS = {"env", "sudo", "time", "command", "nohup", "exec", "builtin"}
GATE_TARGETS = re.compile(
    r"^(lint|lint-web|test[\w-]*|typecheck-web|web-build|web-test|check)$"
)
SHARED_DB = re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^\s'\"]*/ze(?:[\s'\"?]|$)")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2(?=\n|$)", re.S)
MAIN_REFS = {"main", "master"}


def _scrub_heredocs(cmd: str) -> str:
    return HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], cmd)


def _newlines_to_semicolons(cmd: str) -> str:
    out, quote, escaped = [], "", False
    for ch in cmd:
        if escaped:
            escaped = False
        elif ch == "\\" and quote != "'":
            escaped = True
        elif quote:
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "\n":
            ch = ";"
        out.append(ch)
    return "".join(out)


def segments(cmd: str) -> list[tuple[list[str], str]]:
    """Split a command line into (argv, operator-that-follows) pairs."""
    lexer = shlex.shlex(
        _newlines_to_semicolons(_scrub_heredocs(cmd)),
        posix=True,
        punctuation_chars=True,
    )
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = cmd.split()
    result, current = [], []
    for tok in tokens:
        if tok in SEPARATORS:
            if current:
                result.append((current, tok))
            current = []
        else:
            current.append(tok)
    if current:
        result.append((current, ""))
    return result


def _strip_prefix(argv: list[str]) -> tuple[list[str], dict[str, str]]:
    env: dict[str, str] = {}
    while argv:
        head = argv[0]
        if re.fullmatch(r"[A-Za-z_]\w*=.*", head):
            key, _, value = head.partition("=")
            env[key] = value
        elif head in WRAPPERS:
            pass
        else:
            break
        argv = argv[1:]
    return argv, env


def _git_parts(argv: list[str]) -> tuple[str, list[str]]:
    i = 1
    while i < len(argv):
        if argv[i] in ("-C", "-c", "--git-dir", "--work-tree"):
            i += 2
        elif argv[i].startswith("-"):
            i += 1
        else:
            return argv[i], argv[i + 1 :]
    return "", []


def _make_parts(argv: list[str]) -> tuple[list[str], str]:
    targets = [a for a in argv[1:] if not a.startswith("-") and "=" not in a]
    return targets, " ".join(argv[1:])


def _check_git(argv, role):
    sub, rest = _git_parts(argv)
    if sub == "add" and any(a in ("-A", "--all", ".", "-u", "--update") for a in rest):
        return DENY, "Stage explicit paths only (shared worktree): git add <paths>."
    if sub == "stash":
        return DENY, "Never git stash on a shared floor checkout."
    if sub == "push":
        if any(
            a in ("--force", "-f")
            or a.startswith("--force-with-lease")
            or a == "--mirror"
            for a in rest
        ):
            return DENY, "Never force-push."
        if role and role != "maestro":
            refs = [a.split(":")[-1] for a in rest if not a.startswith("-")]
            if any(r in MAIN_REFS for r in refs):
                return DENY, f"Only the Maestro pushes main (ZE_ROLE={role})."
    return None


def _check_make(argv, ctx):
    targets, flat = _make_parts(argv)
    for t in targets:
        if t == "format":
            return (
                DENY,
                "Never run make format (the repo is not globally formatted): ruff format only your files.",
            )
        if t in ("migrate", "migrate-down", "migrate-stamp"):
            return (
                DENY,
                "Never make migrate on a floor: migrate a throwaway ze_e2e_* DB with DATABASE_URL_SYNC set.",
            )
        if t in ("db-reset", "db-reset-seed", "reset-personal-state"):
            return DENY, f"make {t} wipes the shared DB: use a throwaway ze_e2e_* DB."
        if (
            t.startswith("calibrate-")
            and "--check-sets" not in flat
            and "--recall" not in flat
        ):
            return (
                DENY,
                "Live calibration spends credits and needs the user's OK (offline --check-sets and --recall are fine).",
            )
    if (
        any(GATE_TARGETS.match(t) for t in targets)
        and ctx["piped_to_filter"]
        and not ctx["has_pipestatus"]
    ):
        return (
            DENY,
            "Gate output piped to tail/head/grep/tee hides the exit code: run scripts/process/gates.sh or make process-ready.",
        )
    return None


def _check_maestri(argv, role):
    words = [a for a in argv[1:] if not a.startswith("-")]
    if (
        words[:1] == ["role"]
        and words[1:2]
        and words[1] in ("edit", "write", "delete", "assign")
    ):
        return (
            ASK,
            "A role edit restarts every running agent with that role. Check maestri list first and confirm.",
        )
    if words[:2] == ["floor", "land"] or words[:2] == ["floor", "delete"]:
        if role and role != "maestro":
            return DENY, f"Only the Maestro lands or deletes floors (ZE_ROLE={role})."
    if words[:2] == ["floor", "status"] and "review" in argv and "--state" in argv:
        if role in ("eng", "jr"):
            return (
                DENY,
                "Set the review state through make process-ready FLOOR=<name>, which checks the gate receipts first.",
            )
    return None


def decide(cmd: str, env: dict[str, str]) -> tuple[str, str]:
    if not env.get("MAESTRI_TERMINAL_ID"):
        return ALLOW, ""
    role = env.get("ZE_ROLE", "").strip().lower()
    segs = segments(cmd)
    has_pipestatus = "PIPESTATUS" in cmd or "pipefail" in cmd
    if SHARED_DB.search(cmd):
        return DENY, "Never point at the shared DB `ze`: use a throwaway ze_e2e_* DB."
    for idx, (raw, op) in enumerate(segs):
        argv, local_env = _strip_prefix(raw)
        if any(SHARED_DB.search(v) for v in local_env.values()):
            return (
                DENY,
                "Never point at the shared DB `ze`: use a throwaway ze_e2e_* DB.",
            )
        if not argv:
            continue
        if (
            argv[0] in ("bash", "sh", "zsh")
            and "-c" in argv[1:]
            and argv.index("-c") + 1 < len(argv)
        ):
            verdict = decide(argv[argv.index("-c") + 1], env)
            if verdict[0] != ALLOW:
                return verdict
            continue
        piped = (
            op in ("|", "|&")
            and idx + 1 < len(segs)
            and (
                _strip_prefix(segs[idx + 1][0])[0][:1]
                and _strip_prefix(segs[idx + 1][0])[0][0]
                in ("tail", "head", "grep", "tee")
            )
        )
        ctx = {"piped_to_filter": bool(piped), "has_pipestatus": has_pipestatus}
        if argv[0] == "uv" and argv[1:2] == ["run"]:
            argv = argv[2:] or argv
        head = os.path.basename(argv[0])
        result = None
        if head == "git":
            result = _check_git(argv, role)
        elif head == "make":
            result = _check_make(argv, ctx)
        elif head == "maestri" or argv[0] == os.environ.get("MAESTRI_CLI"):
            result = _check_maestri(argv, role)
        elif head == "psql" and any(
            a == "-d" and i + 1 < len(argv) and argv[i + 1] == "ze"
            for i, a in enumerate(argv)
        ):
            result = (
                DENY,
                "Never point at the shared DB `ze`: use a throwaway ze_e2e_* DB.",
            )
        if result:
            return result
    return ALLOW, ""


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    verdict, why = decide(
        data.get("tool_input", {}).get("command", ""), dict(os.environ)
    )
    if verdict == DENY:
        print(f"BLOCKED by Ze process guard: {why}", file=sys.stderr)
        return 2
    if verdict == ASK:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": f"Ze process guard: {why}",
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
