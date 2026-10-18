import importlib.util
import json
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


def test_precommit_blocks_telemetry_key_and_arch_notes(tmp_path):
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
    (tmp_path / "ctx").mkdir()
    (tmp_path / "ctx" / ".spec-context.json").write_text(
        '{"telemetryInstanceId": "abc"}'
    )
    _git(tmp_path, "add", "specs", "ctx")
    assert _precommit(tmp_path, {}).returncode == 0
    p = _precommit(tmp_path, {"MAESTRI_TERMINAL_ID": "T", "ZE_ROLE": "eng"})
    assert p.returncode == 1
    assert "telemetryInstanceId" in p.stderr and "specs/arch" in p.stderr
    assert (
        _precommit(tmp_path, {"MAESTRI_TERMINAL_ID": "T", "SKIP": "1"}).returncode == 0
    )
