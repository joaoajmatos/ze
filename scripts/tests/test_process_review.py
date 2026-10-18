import json
import os
import stat
import subprocess
import time
from pathlib import Path

import pytest
from conftest import PROCESS, load_process_module

brief_lint = load_process_module("brief_lint")
recruit = load_process_module("recruit")

GOOD_BRIEF = (
    "State file: journal/state/ID.md. Scratchpad: use your own. Pre-review checklist applies. "
    "Trailer: Co-Authored-By. Reviewer: Gauge. Use a throwaway DB ze_e2e_x."
)


def test_brief_lint_passes_a_complete_brief_and_names_each_gap():
    assert brief_lint.lint(GOOD_BRIEF) == []
    assert brief_lint.lint("hello") == list(brief_lint.REQUIRED)
    assert "throwaway DB (ze_e2e_*)" in brief_lint.lint(
        GOOD_BRIEF.replace("throwaway", "x").replace("ze_e2e_", "y")
    )


@pytest.mark.parametrize(
    ("role", "tier", "ok"),
    [
        ("eng", "sonnet", True),
        ("eng", "opus", False),
        ("jr", "haiku", True),
        ("review", "haiku", False),
        ("architect", "opus", True),
        ("maestro", "sonnet", False),
    ],
)
def test_tier_table(role, tier, ok):
    config = recruit.load_roles()
    if ok:
        command, _ = recruit.command_for(config, role, tier)
        assert command.startswith(f"ZE_ROLE={role} claude")
    else:
        with pytest.raises(SystemExit):
            recruit.command_for(config, role, tier)


def test_tier_table_matches_the_model_tier_memory_rules():
    roles = recruit.load_roles()["roles"]
    assert (
        "opus" not in roles["eng"]["allowed"]
        and "opus" not in roles["review"]["allowed"]
    )
    assert roles["architect"]["allowed"] == ["opus"]


FAKE = """#!/usr/bin/env bash
echo "$@" >> "$FAKE_LOG"
case "$1" in
  check) echo "$FAKE_CHECK";;
  ask) echo "$FAKE_ASK";;
  note) exit 1;;
esac
"""


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    cli = tmp_path / "maestri"
    cli.write_text(FAKE)
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("MAESTRI_CLI", str(cli))
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("FAKE_CHECK", "❯ ready for input")
    monkeypatch.setenv("FAKE_ASK", "ready")
    for k in ("BOOT", "REPLY", "POLL"):
        monkeypatch.setenv(f"ZE_RECRUIT_{k}_SECS", "1" if k != "POLL" else "0.1")
    return log


def calls(log: Path) -> list[str]:
    return log.read_text().splitlines() if log.exists() else []


def test_recruit_happy_path(fake_cli, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brief = tmp_path / "brief.md"
    brief.write_text(GOOD_BRIEF)
    assert recruit.main(["Forge", "eng", "sonnet", "F", str(brief)]) == 0
    lines = calls(fake_cli)
    assert lines[0].startswith(
        "recruit Forge --role Engineer --floor F --command ZE_ROLE=eng claude"
    )
    assert any(line.startswith("ask Forge") for line in lines)
    assert not any("--replace" in line for line in lines)


def test_recruit_replaces_once_when_the_agent_never_replies(
    fake_cli, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FAKE_ASK", "zzz")
    brief = tmp_path / "brief.md"
    brief.write_text(GOOD_BRIEF)
    assert recruit.main(["Forge", "eng", "sonnet", "F", str(brief)]) == 1
    lines = calls(fake_cli)
    assert sum("--replace" in line for line in lines) == 1
    assert sum(line.startswith("ask Forge") for line in lines) == 2


def test_recruit_refuses_a_bad_brief_before_calling_maestri(
    fake_cli, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    brief = tmp_path / "brief.md"
    brief.write_text("do things")
    assert recruit.main(["Forge", "eng", "sonnet", "F", str(brief)]) == 1
    assert calls(fake_cli) == []


def _repo(tmp_path):
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "a@b"],
        ["config", "user.name", "t"],
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    shas = []
    for i in range(3):
        (tmp_path / f"f{i}").write_text("x")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", str(i)], cwd=tmp_path, check=True)
        if i == 0:
            subprocess.run(
                ["git", "checkout", "-q", "-b", "feat"], cwd=tmp_path, check=True
            )
        shas.append(
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    return shas


def review(*args, repo):
    return subprocess.run(
        ["python3", str(PROCESS / "review.py"), *args, "--repo", str(repo)],
        capture_output=True,
        text=True,
        env=os.environ,
    )


def test_review_request_verdict_flow_and_contiguity(fake_cli, tmp_path, monkeypatch):
    a, b, c = _repo(tmp_path)
    monkeypatch.setenv("FAKE_CHECK", "working...")
    p = review("request", f"{a}..{b}", "Gauge", "--wait", "0", repo=tmp_path)
    assert (
        "ALERT" in p.stderr and p.returncode == 1
    )  # unchanged terminal = never started
    record = json.loads(
        next((tmp_path / ".process" / "reviews").glob("*.json")).read_text()
    )
    assert record["state"] == "requested" and record["from"] == a and record["to"] == b

    gap = review("request", f"{c}..{c}", "Gauge", "--wait", "0", repo=tmp_path)
    assert gap.returncode == 1
    skip = review("request", f"{a}..{c}", "Gauge", "--wait", "0", repo=tmp_path)
    assert "delta-only" in skip.stderr

    findings = tmp_path / "f.txt"
    findings.write_text("M1 something")
    assert (
        review("verdict", f"{a}..{b}", "CHANGES", repo=tmp_path).returncode == 1
    )  # needs findings
    ok = review(
        "verdict", f"{a}..{b}", "CHANGES", "--findings", str(findings), repo=tmp_path
    )
    assert ok.returncode == 0, ok.stderr
    record = json.loads(
        next((tmp_path / ".process" / "reviews").glob("*.json")).read_text()
    )
    assert record["verdict"] == "CHANGES" and record["state"] == "delivered"
    assert any("M1 something" in line for line in calls(fake_cli))

    nxt = review("request", f"{b}..{c}", "Gauge", "--wait", "0", repo=tmp_path)
    assert "delta-only" not in nxt.stderr


def test_review_verdict_without_request_is_refused(fake_cli, tmp_path):
    a, b, _ = _repo(tmp_path)
    p = review("verdict", f"{a}..{b}", "APPROVE", repo=tmp_path)
    assert p.returncode == 1 and "no review request" in p.stderr


def test_stop_gate_blocks_undelivered_verdict_once(tmp_path):
    _repo(tmp_path)
    reviews = tmp_path / ".process" / "reviews"
    reviews.mkdir(parents=True)
    (reviews / "a..b.json").write_text(json.dumps({"state": "requested"}))
    stop_gate = load_process_module_from_hooks("stop_gate")
    env = {"MAESTRI_TERMINAL_ID": "T", "ZE_ROLE": "review"}
    assert "no verdict record" in stop_gate.decide({"cwd": str(tmp_path)}, env)
    assert stop_gate.decide({"cwd": str(tmp_path), "stop_hook_active": True}, env) == ""
    assert stop_gate.decide({"cwd": str(tmp_path)}, {"ZE_ROLE": "review"}) == ""
    (reviews / "a..b.json").write_text(json.dumps({"state": "delivered"}))
    assert stop_gate.decide({"cwd": str(tmp_path)}, env) == ""


def test_stop_gate_flags_a_stale_state_file(tmp_path):
    _repo(tmp_path)
    state = tmp_path / "journal" / "state"
    state.mkdir(parents=True)
    file = state / "T.md"
    file.write_text("x")
    old = time.time() - 3600
    os.utime(file, (old, old))
    stop_gate = load_process_module_from_hooks("stop_gate")
    env = {"MAESTRI_TERMINAL_ID": "T", "ZE_ROLE": "eng"}
    assert "state file" in stop_gate.decide({"cwd": str(tmp_path)}, env)
    os.utime(file, None)
    assert stop_gate.decide({"cwd": str(tmp_path)}, env) == ""
    assert stop_gate.decide({"cwd": str(tmp_path)}, {**env, "ZE_ROLE": "maestro"}) == ""


def load_process_module_from_hooks(name):
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        name, PROCESS / "hooks" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


STUCK_CLI = """#!/usr/bin/env bash
echo "$@" >> "$FAKE_LOG"
case "$1" in
  check) if grep -q -- "--raw" "$FAKE_LOG"; then echo "⏺ ready"; else echo "❯ $(head -c 40 "$FAKE_BRIEF")"; fi;;
  ask) echo "";;
esac
"""


def test_recruit_submits_a_brief_stuck_in_the_input_box(tmp_path, monkeypatch):
    cli = tmp_path / "maestri"
    cli.write_text(STUCK_CLI)
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "calls.log"
    brief = tmp_path / "brief.md"
    brief.write_text(GOOD_BRIEF)
    monkeypatch.setenv("MAESTRI_CLI", str(cli))
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("FAKE_BRIEF", str(brief))
    monkeypatch.setenv("ZE_RECRUIT_BOOT_SECS", "1")
    monkeypatch.setenv("ZE_RECRUIT_REPLY_SECS", "2")
    monkeypatch.setenv("ZE_RECRUIT_POLL_SECS", "0.1")
    monkeypatch.chdir(tmp_path)
    assert recruit.main(["Forge", "eng", "sonnet", "F", str(brief)]) == 0
    assert any("--raw" in line for line in calls(log))
    assert not any("--replace" in line for line in calls(log))
