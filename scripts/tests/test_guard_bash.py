import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).parents[1] / "process" / "hooks" / "guard_bash.py"
_SPEC = importlib.util.spec_from_file_location("guard_bash", HOOK)
guard = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = guard
_SPEC.loader.exec_module(guard)

AGENT = {"MAESTRI_TERMINAL_ID": "T1"}

CASES = [
    ("git add -A", "deny"),
    ("git add .", "deny"),
    ("git add --all", "deny"),
    ("git add -u", "deny"),
    ("git -C sub add .", "deny"),
    ("git add apps/ze-web/src/a.ts", "allow"),
    ("git add ./apps/x.py", "allow"),
    ("git stash push", "deny"),
    ("git commit -m 'explain why git stash is banned'", "allow"),
    ("git commit -m \"$(cat <<'EOF'\nfix\n\ngit stash notes\nEOF\n)\"", "allow"),
    ("git push remote process-kit", "allow"),
    ("git push --force remote x", "deny"),
    ("git push -f", "deny"),
    ("git push --force-with-lease remote x", "deny"),
    ("make format", "deny"),
    ("uv run ruff format core/x.py", "allow"),
    ("make migrate", "deny"),
    ("make migrate-stamp", "deny"),
    ("make db-reset", "deny"),
    (
        "DATABASE_URL_SYNC=postgresql+psycopg2://ze:ze@localhost:5432/ze_e2e_187 uv run alembic upgrade heads",
        "allow",
    ),
    (
        "DATABASE_URL_SYNC=postgresql+psycopg2://ze:ze@localhost:5432/ze uv run alembic upgrade heads",
        "deny",
    ),
    ("psql postgresql://ze:ze@localhost:5432/ze -c 'drop table x'", "deny"),
    ("psql postgresql://ze:ze@localhost:5432/ze_e2e_1 -c 'select 1'", "allow"),
    ("psql -h localhost -d ze -c 'select 1'", "deny"),
    ("make calibrate-routing", "deny"),
    ("make calibrate-routing ARGS=--check-sets", "allow"),
    ("make calibrate-skills ARGS=--recall", "allow"),
    ("make test-py 2>&1 | tail -5", "deny"),
    ("make lint-web | grep error", "deny"),
    ("make check | tee out.log", "deny"),
    ("make test-py 2>&1 | tail -5; echo ${PIPESTATUS[0]}", "allow"),
    ("make test-py > out.txt 2>&1; echo rc=$?", "allow"),
    ("make lint-web", "allow"),
    ("grep -r foo . | tail", "allow"),
    ("bash -c 'make migrate'", "deny"),
    ("cd x && git stash", "deny"),
    ("maestri role edit Reviewer old new", "ask"),
    ("maestri role write Reviewer 'p'", "ask"),
    ("maestri role list", "allow"),
    ("maestri ask Cartographer hi", "allow"),
]


@pytest.mark.parametrize(("cmd", "want"), CASES)
def test_decision_table(cmd, want):
    assert guard.decide(cmd, AGENT)[0] == want


@pytest.mark.parametrize(("cmd", "want"), CASES)
def test_noop_without_maestri_terminal(cmd, want):
    assert guard.decide(cmd, {})[0] == "allow"


@pytest.mark.parametrize(
    ("role", "cmd", "want"),
    [
        ("maestro", "git push remote main", "allow"),
        ("eng", "git push remote main", "deny"),
        ("eng", "git push remote HEAD:main", "deny"),
        ("eng", "git push remote process-kit", "allow"),
        ("", "git push remote main", "allow"),
        ("maestro", "maestri floor land F --into main", "allow"),
        ("review", "maestri floor land F --into main", "deny"),
        ("eng", "maestri floor delete F", "deny"),
        ("eng", "maestri floor status F --state review", "deny"),
        ("jr", "maestri floor status F --state review", "deny"),
        # 2026-10-22: Fathom (architect) set 198 to review when only the spec work was done.
        ("architect", "maestri floor status F --state review", "deny"),
        ("review", "maestri floor status F --state review", "deny"),
        ("docs", "maestri floor status F --state review", "deny"),
        ("eng", "maestri floor status F --state building", "allow"),
        ("maestro", "maestri floor status F --state review", "allow"),
        ("", "maestri floor status F --state review", "allow"),
    ],
)
def test_role_rules(role, cmd, want):
    assert guard.decide(cmd, {**AGENT, "ZE_ROLE": role})[0] == want


def _run(payload, env_extra):
    import os

    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("MAESTRI_TERMINAL_ID", "ZE_ROLE")
    }
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )


def test_exit_contract_deny():
    p = _run({"tool_name": "Bash", "tool_input": {"command": "git add -A"}}, AGENT)
    assert p.returncode == 2
    assert "BLOCKED" in p.stderr


def test_exit_contract_ask():
    p = _run(
        {"tool_name": "Bash", "tool_input": {"command": "maestri role edit R a b"}},
        AGENT,
    )
    assert p.returncode == 0
    assert json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_exit_contract_noop_outside_maestri():
    assert (
        _run(
            {"tool_name": "Bash", "tool_input": {"command": "git add -A"}}, {}
        ).returncode
        == 0
    )


def test_bad_stdin_does_not_block():
    p = subprocess.run(
        [sys.executable, str(HOOK)], input="not json", text=True, capture_output=True
    )
    assert p.returncode == 0


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _precommit(repo, env_extra):
    import os

    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("MAESTRI_TERMINAL_ID", "ZE_ROLE", "SKIP")
    }
    env.update(env_extra)
    script = Path(__file__).parents[1] / "process" / "precommit_checks.sh"
    return subprocess.run(
        ["bash", str(script)], cwd=repo, capture_output=True, text=True, env=env
    )


def test_precommit_blocks_arch_notes(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(
        tmp_path,
        "-c",
        "user.email=a@b",
        "-c",
        "user.name=t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "i",
    )
    (tmp_path / "specs" / "arch").mkdir(parents=True)
    (tmp_path / "specs" / "arch" / "note.md").write_text("x")
    _git(tmp_path, "add", "specs")
    assert _precommit(tmp_path, {}).returncode == 0
    p = _precommit(tmp_path, {"MAESTRI_TERMINAL_ID": "T", "ZE_ROLE": "eng"})
    assert p.returncode == 1
    assert "specs/arch" in p.stderr
    assert (
        _precommit(tmp_path, {"MAESTRI_TERMINAL_ID": "T", "SKIP": "1"}).returncode == 0
    )


LAND = ["lint", "test-py", "test-web", "typecheck-web", "lint-web"]


def _receipt(repo, sha, gates, dirty=0):
    receipts = repo / ".process" / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / f"{sha}.json").write_text(
        json.dumps(
            {"dirty_files": dirty, "gates": [{"gate": g, "rc": rc} for g, rc in gates]}
        )
    )


def _main_repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(
        tmp_path,
        "-c",
        "user.email=a@b",
        "-c",
        "user.name=t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "i",
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()


def test_push_main_needs_a_green_receipt_with_every_land_gate(tmp_path):
    sha = _main_repo(tmp_path)
    env = {**AGENT, "ZE_ROLE": "maestro"}
    cmd = "git push remote main"
    assert guard.decide(cmd, env, str(tmp_path))[0] == "deny"
    _receipt(tmp_path, sha, [(g, 1 if g == "lint" else 0) for g in LAND])
    verdict, why = guard.decide(cmd, env, str(tmp_path))
    assert verdict == "deny" and "not green" in why
    _receipt(tmp_path, sha, [])  # H1: an empty receipt is not a green one
    verdict, why = guard.decide(cmd, env, str(tmp_path))
    assert verdict == "deny" and "lacks the land gates" in why
    _receipt(tmp_path, sha, [("lint", 0)])
    assert "lacks the land gates" in guard.decide(cmd, env, str(tmp_path))[1]
    _receipt(tmp_path, sha, [(g, 0) for g in LAND])
    assert guard.decide(cmd, env, str(tmp_path))[0] == "allow"
    assert guard.decide("git push remote process-kit", env, str(tmp_path))[0] == "allow"


@pytest.mark.parametrize(
    "before",
    [
        "git commit -q -m x",
        "git -C . merge feat",
        "git pull --rebase remote main",
        'maestri floor land "F" --into main',
    ],
)
def test_push_main_after_a_head_move_in_the_same_command_is_refused(tmp_path, before):
    """The receipt check runs before the command, so it would see the old HEAD (f3df9298 slipped through)."""
    sha = _main_repo(tmp_path)
    env = {**AGENT, "ZE_ROLE": "maestro"}
    _receipt(tmp_path, sha, [(g, 0) for g in LAND])
    assert guard.decide("git push remote main", env, str(tmp_path))[0] == "allow"
    verdict, why = guard.decide(
        f"{before} && git push -q remote main", env, str(tmp_path)
    )
    assert verdict == "deny" and "its own command" in why
    assert (
        guard.decide(f"{before} && git push remote feat", env, str(tmp_path))[0]
        == "allow"
    )


def _commit_file(repo, name):
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text("x")
    _git(repo, "add", name)
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-q", "-m", name)


def test_push_main_allows_specs_and_docs_only_commits_after_a_green_receipt(tmp_path):
    sha = _main_repo(tmp_path)
    env = {**AGENT, "ZE_ROLE": "maestro"}
    cmd = "git push remote main"
    _receipt(tmp_path, sha, [(g, 0) for g in LAND])
    _commit_file(tmp_path, "specs/phases/999-x/spec.md")
    _commit_file(tmp_path, "docs/process.md")
    assert guard.decide(cmd, env, str(tmp_path))[0] == "allow"
    _commit_file(tmp_path, "apps/ze-web/src/a.ts")
    verdict, why = guard.decide(cmd, env, str(tmp_path))
    assert verdict == "deny" and "no gate receipt" in why


def test_docs_only_push_needs_the_ancestor_receipt_green(tmp_path):
    sha = _main_repo(tmp_path)
    env = {**AGENT, "ZE_ROLE": "maestro"}
    _receipt(tmp_path, sha, [(g, 1 if g == "lint" else 0) for g in LAND])
    _commit_file(tmp_path, "specs/a.md")
    assert guard.decide("git push remote main", env, str(tmp_path))[0] == "deny"


def test_bare_and_head_pushes_from_main_are_checked(tmp_path):
    _main_repo(tmp_path)
    env = {**AGENT, "ZE_ROLE": "maestro"}
    for cmd in (
        "git push",
        "git push remote",
        "git push remote HEAD",
        "git push -u remote HEAD",
    ):
        assert guard.decide(cmd, env, str(tmp_path))[0] == "deny", cmd
    assert (
        guard.decide(
            "git push remote HEAD", {**AGENT, "ZE_ROLE": "eng"}, str(tmp_path)
        )[0]
        == "deny"
    )
    _git(tmp_path, "checkout", "-q", "-b", "feat")
    assert guard.decide("git push", env, str(tmp_path))[0] == "allow"


def test_git_dash_c_push_checks_that_directory(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    sha = _main_repo(other)
    env = {**AGENT, "ZE_ROLE": "maestro"}
    cmd = f"git -C {other} push remote main"
    assert "no gate receipt" in guard.decide(cmd, env, str(tmp_path))[1]
    _receipt(other, sha, [(g, 0) for g in LAND])
    assert guard.decide(cmd, env, str(tmp_path))[0] == "allow"


@pytest.mark.parametrize(
    ("cmd", "want"),
    [
        ("git commit -a -m x", "deny"),
        ("git commit -am x", "deny"),
        ("git commit --all", "deny"),
        ("git commit -m 'work on a thing'", "allow"),
        ("git commit --amend --no-edit", "allow"),
        ('"$MAESTRI_CLI" floor land F --into main', "deny"),
        ("${MAESTRI_CLI} floor delete F", "deny"),
        ('"$MAESTRI_CLI" ask Gauge hi', "allow"),
    ],
)
def test_m5_gaps(cmd, want):
    assert guard.decide(cmd, {**AGENT, "ZE_ROLE": "eng"})[0] == want


@pytest.mark.parametrize("role", ["web", "platform"])
def test_new_builder_roles_cannot_set_review(role):
    assert (
        guard.decide(
            "maestri floor status F --state review", {**AGENT, "ZE_ROLE": role}
        )[0]
        == "deny"
    )


def test_post_bash_stamps_only_after_a_commit(tmp_path):
    """N1: the stamp comes from a PostToolUse hook, so a refused commit (guard deny) never leaves one."""
    _main_repo(tmp_path)
    post = Path(guard.__file__).parent / "post_bash.py"
    marker = tmp_path / ".process" / "own-commit-T9"

    def run(command, terminal="T9"):
        env = {k: v for k, v in os.environ.items() if k != "MAESTRI_TERMINAL_ID"}
        if terminal:
            env["MAESTRI_TERMINAL_ID"] = terminal
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": str(tmp_path),
        }
        return subprocess.run(
            [sys.executable, str(post)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
        )

    assert run("git status").returncode == 0 and not marker.exists()
    assert run("git commit -m x", terminal="").returncode == 0 and not marker.exists()
    assert run("git commit -m x").returncode == 0 and marker.exists()
    marker.unlink()
    assert (
        run("git add a.py && git commit -m 'fix: x'").returncode == 0
        and marker.exists()
    )
    marker.unlink()
    assert (
        run(f"git -C {tmp_path} commit --amend --no-edit").returncode == 0
        and marker.exists()
    )
    marker.unlink()
    assert run("echo git commit").returncode == 0 and not marker.exists()
    # the guard itself no longer writes the stamp
    guard.decide(
        "git commit -m x",
        {**AGENT, "MAESTRI_TERMINAL_ID": "T9", "ZE_ROLE": "eng"},
        str(tmp_path),
    )
    assert not marker.exists()
