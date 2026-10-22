#!/usr/bin/env python3
"""PreToolUse(Bash) guard for Ze agents (Claude Code hook contract).

Exit 2 + stderr blocks the call; exit 0 with a permissionDecision JSON on stdout asks the user.
A no-op unless MAESTRI_TERMINAL_ID is set, so a person's own shell keeps working.
ZE_ROLE (maestro|architect|eng|web|platform|jr|review|ground-review|qa|docs) scopes the role rules; unset means unrestricted.
It catches mistakes, not adversaries: receipts and land preflight are the real gate.
"""

import json
import os
import re
import shlex
import subprocess
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
BUILDERS = {"eng", "web", "platform", "jr"}
LAND_GATES = {"lint", "test-py", "test-web", "typecheck-web", "lint-web"}
MAESTRI_CLI_SPELLINGS = ("$MAESTRI_CLI", "${MAESTRI_CLI}")
COMMIT_ALL = re.compile(r"^-[a-zA-Z]*a[a-zA-Z]*$")
HEAD_MOVERS = {
    "commit",
    "merge",
    "pull",
    "rebase",
    "cherry-pick",
    "am",
    "revert",
    "reset",
    "checkout",
    "switch",
}


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


def _git_parts(argv: list[str]) -> tuple[str, list[str], str]:
    """(subcommand, its args, the -C directory or empty)."""
    i, workdir = 1, ""
    while i < len(argv):
        if argv[i] == "-C" and i + 1 < len(argv):
            workdir = argv[i + 1]
            i += 2
        elif argv[i] in ("-c", "--git-dir", "--work-tree"):
            i += 2
        elif argv[i].startswith("-"):
            i += 1
        else:
            return argv[i], argv[i + 1 :], workdir
    return "", [], workdir


def _make_parts(argv: list[str]) -> tuple[list[str], str]:
    targets = [a for a in argv[1:] if not a.startswith("-") and "=" not in a]
    return targets, " ".join(argv[1:])


def _receipt_problem(cwd: str) -> str:
    """Why HEAD in cwd has no green gate receipt, or empty when it has one."""
    head = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "HEAD"], capture_output=True, text=True
    )
    top = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if head.returncode or top.returncode:
        return ""
    sha = head.stdout.strip()
    path = os.path.join(top.stdout.strip(), ".process", "receipts", f"{sha}.json")
    try:
        with open(path) as fh:
            receipt = json.load(fh)
    except (OSError, ValueError):
        if _docs_only_since_green(cwd, top.stdout.strip()):
            return ""
        return (
            f"no gate receipt for HEAD {sha[:8]}: run make process-gates PROFILE=land"
        )
    return _receipt_verdict(receipt, sha)


def _receipt_verdict(receipt: dict, sha: str) -> str:
    names = {g.get("gate") for g in receipt.get("gates", [])}
    failing = [g["gate"] for g in receipt.get("gates", []) if g.get("rc")]
    if failing or receipt.get("dirty_files") or receipt.get("ok") is False:
        return f"gate receipt for HEAD {sha[:8]} is not green (failing: {failing or 'checks'})"
    if missing := sorted(LAND_GATES - names):
        return f"gate receipt for HEAD {sha[:8]} lacks the land gates: {', '.join(missing)} (run make process-gates PROFILE=land)"
    return ""


def _is_docs_path(path: str) -> bool:
    return path.startswith("specs/") or (
        path.endswith(".md") and (path.startswith("docs/") or "/" not in path)
    )


def _docs_only_since_green(cwd: str, top: str) -> bool:
    """HEAD has no receipt, but an ancestor has a green land receipt and only specs/docs changed since."""
    revs = subprocess.run(
        ["git", "-C", cwd, "rev-list", "--first-parent", "-n", "50", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.split()
    for rev in revs[1:]:
        path = os.path.join(top, ".process", "receipts", f"{rev}.json")
        try:
            with open(path) as fh:
                receipt = json.load(fh)
        except (OSError, ValueError):
            continue
        if _receipt_verdict(receipt, rev):
            return False
        diff = subprocess.run(
            ["git", "-C", cwd, "diff", "--name-only", rev, "HEAD"],
            capture_output=True,
            text=True,
        )
        files = diff.stdout.split()
        return diff.returncode == 0 and all(_is_docs_path(f) for f in files)
    return False


def _current_branch(cwd: str) -> str:
    p = subprocess.run(
        ["git", "-C", cwd or ".", "symbolic-ref", "--short", "-q", "HEAD"],
        capture_output=True,
        text=True,
    )
    return p.stdout.strip()


def _check_git(argv, role, cwd, head_moved=False):
    sub, rest, workdir = _git_parts(argv)
    where = os.path.join(cwd, workdir) if cwd and workdir else (workdir or cwd)
    if sub == "add" and any(a in ("-A", "--all", ".", "-u", "--update") for a in rest):
        return DENY, "Stage explicit paths only (shared worktree): git add <paths>."
    if sub == "commit" and any(a == "--all" or COMMIT_ALL.match(a) for a in rest):
        return (
            DENY,
            "git commit -a would commit other agents' edits on a shared floor: git add <paths>, then git commit.",
        )
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
        positional = [a for a in rest if not a.startswith("-")]
        refs = [a.split(":")[-1] for a in positional[1:]] or [_current_branch(where)]
        refs = [_current_branch(where) if r == "HEAD" else r for r in refs]
        if any(r in MAIN_REFS for r in refs):
            if role and role != "maestro":
                return DENY, f"Only the Maestro pushes main (ZE_ROLE={role})."
            if head_moved:
                # the receipt check below sees HEAD before the earlier command moves it
                return (
                    DENY,
                    "Push main in its own command, after the commit or merge: the receipt check needs the HEAD being pushed.",
                )
            problem = _receipt_problem(where) if where else ""
            if problem:
                return DENY, problem
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
        if role in BUILDERS:
            return (
                DENY,
                "Set the review state through make process-ready FLOOR=<name>, which checks the gate receipts first.",
            )
    return None


def decide(cmd: str, env: dict[str, str], cwd: str = "") -> tuple[str, str]:
    if not env.get("MAESTRI_TERMINAL_ID"):
        return ALLOW, ""
    role = env.get("ZE_ROLE", "").strip().lower()
    segs = segments(cmd)
    has_pipestatus = "PIPESTATUS" in cmd or "pipefail" in cmd
    if SHARED_DB.search(cmd):
        return DENY, "Never point at the shared DB `ze`: use a throwaway ze_e2e_* DB."
    head_moved = False
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
            verdict = decide(argv[argv.index("-c") + 1], env, cwd)
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
            result = _check_git(argv, role, cwd, head_moved)
            head_moved = head_moved or _git_parts(argv)[0] in HEAD_MOVERS
        elif head == "make":
            result = _check_make(argv, ctx)
        elif (
            head == "maestri"
            or argv[0] in MAESTRI_CLI_SPELLINGS
            or argv[0] == os.environ.get("MAESTRI_CLI")
        ):
            result = _check_maestri(argv, role)
            head_moved = head_moved or argv[1:3] == ["floor", "land"]
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
        data.get("tool_input", {}).get("command", ""),
        dict(os.environ),
        data.get("cwd", ""),
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
