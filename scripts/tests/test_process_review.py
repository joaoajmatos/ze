import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path

import pytest
from conftest import PROCESS, load_hook, load_process_module

brief_lint = load_process_module("brief_lint")
recruit = load_process_module("recruit")
stop_gate = load_hook("stop_gate")

ROLE_LIST = Path(__file__).with_name("fixtures_role_list.txt").read_text()
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
        ("web", "sonnet", True),
        ("web", "opus", False),
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


def test_command_carries_the_agent_name():
    command, _ = recruit.command_for(recruit.load_roles(), "eng", "sonnet", "Forge")
    assert command.startswith("ZE_ROLE=eng ZE_AGENT=Forge claude")


def test_tier_table_matches_the_model_tier_memory_rules():
    roles = recruit.load_roles()["roles"]
    for role in ("eng", "web", "platform", "review", "ground-review"):
        assert "opus" not in roles[role]["allowed"]
    assert roles["architect"]["allowed"] == ["opus"]


def test_maestri_role_names_exist_in_the_workspace():
    """Every maestri_role in roles.toml is a role that `maestri role list` prints; the Maestro has none."""
    real = set(re.findall(r'^  - "([^"]+)"', ROLE_LIST, re.M))
    assert "Backend Engineer" in real
    roles = recruit.load_roles()["roles"]
    for name, role in roles.items():
        if name == "maestro":
            assert "maestri_role" not in role
        else:
            assert role["maestri_role"] in real, (
                f"{name}: {role['maestri_role']!r} is not a Maestri role"
            )


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


def _brief(tmp_path):
    brief = tmp_path / "brief.md"
    brief.write_text(GOOD_BRIEF)
    return brief


def test_recruit_happy_path(fake_cli, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert recruit.main(["Forge", "eng", "sonnet", "F", str(_brief(tmp_path))]) == 0
    lines = calls(fake_cli)
    assert lines[0].startswith(
        "recruit Forge --role Backend Engineer --floor F --command ZE_ROLE=eng ZE_AGENT=Forge claude"
    )
    assert any(line.startswith("ask Forge") for line in lines)
    assert not any(line.startswith("dismiss") for line in lines)


def test_recruit_maestro_gets_no_role(fake_cli, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recruit.main(["Boss", "maestro", "opus", "F", str(_brief(tmp_path))])
    assert "--role" not in calls(fake_cli)[0]


def test_recruit_starts_over_once_when_the_agent_never_replies(
    fake_cli, tmp_path, monkeypatch
):
    """L3: --replace keeps no --role or --command, so the retry dismisses and recruits again with them."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FAKE_ASK", "zzz")
    assert recruit.main(["Forge", "eng", "sonnet", "F", str(_brief(tmp_path))]) == 1
    lines = calls(fake_cli)
    assert not any("--replace" in line for line in lines)
    assert sum(line.startswith("dismiss Forge") for line in lines) == 1
    recruits = [line for line in lines if line.startswith("recruit Forge")]
    assert len(recruits) == 2 and recruits[0] == recruits[1]
    assert sum(line.startswith("ask Forge") for line in lines) == 2


def test_the_echoed_ping_is_not_a_ready_reply(fake_cli, tmp_path, monkeypatch):
    """M3: the ask output carries the screen, which echoes 'Reply with one line ready'."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "FAKE_ASK", "❯ brief... Reply with one line 'ready' first, then work."
    )
    assert recruit.main(["Forge", "eng", "sonnet", "F", str(_brief(tmp_path))]) == 1


@pytest.mark.parametrize(
    ("screen", "want"),
    [
        ("ready", True),
        ("⏺ ready", True),
        ("⏺ Ready.", True),
        ("Reply with one line 'ready' first", False),
        ("not ready yet", False),
        ("already ready to go", False),
    ],
)
def test_said_ready(screen, want):
    assert recruit.said_ready(screen) is want


def test_recruit_refuses_a_bad_brief_before_calling_maestri(
    fake_cli, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    brief = tmp_path / "brief.md"
    brief.write_text("do things")
    assert recruit.main(["Forge", "eng", "sonnet", "F", str(brief)]) == 1
    assert calls(fake_cli) == []


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
    brief = _brief(tmp_path)
    monkeypatch.setenv("MAESTRI_CLI", str(cli))
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("FAKE_BRIEF", str(brief))
    monkeypatch.setenv("ZE_RECRUIT_BOOT_SECS", "1")
    monkeypatch.setenv("ZE_RECRUIT_REPLY_SECS", "2")
    monkeypatch.setenv("ZE_RECRUIT_POLL_SECS", "0.1")
    monkeypatch.chdir(tmp_path)
    assert recruit.main(["Forge", "eng", "sonnet", "F", str(brief)]) == 0
    assert any("--raw" in line for line in calls(log))
    assert not any(line.startswith("dismiss") for line in calls(log))


def _repo(tmp_path):
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "a@b"],
        ["config", "user.name", "t"],
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    shas = []
    for i in range(4):
        (tmp_path / f"f{i}").write_text("x")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", str(i)], cwd=tmp_path, check=True)
        shas.append(
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        if i == 0:
            subprocess.run(
                ["git", "checkout", "-q", "-b", "feat"], cwd=tmp_path, check=True
            )
    return shas


REVIEW_CLI = """#!/usr/bin/env bash
echo "$@" >> "$FAKE_LOG"
asked() { grep -c '^ask Gauge .rq' "$FAKE_LOG"; }
raw() { grep -c -- '--raw' "$FAKE_LOG"; }
marks() { i=0; while [ "$i" -lt "$1" ]; do echo "⏺ reading the diff"; i=$((i+1)); done; }
case "$1" in
  check)
    case "$FAKE_MODE" in
      idle) echo "welcome screen";;
      oldtoken) echo "❯ [rqold000] Review aaaa..bbbb in /x (read-only). make process-review-verdict";;
      busy) echo "⏺ reading the diff"; echo "✽ Brewing… (1m · esc to interrupt)";;
      stuckforever) echo "❯ $(grep '^ask Gauge .rq' "$FAKE_LOG" | tail -1)";;
      active) marks "$(asked)";;
      stuck) if [ "$(raw)" -ge 1 ]; then marks "$(raw)"; else echo "❯ $(grep '^ask Gauge .rq' "$FAKE_LOG" | tail -1)"; fi;;
    esac;;
  ask) if [ -n "$FAKE_UNCONNECTED" ] && [ "$2" != "Claude Code" ] && echo " $FAKE_UNCONNECTED " | grep -q " $2 "; then
         echo "maestri: Terminal '$2' not found" >&2; exit 1; fi; echo "";;
  note) exit 1;;
esac
"""


@pytest.fixture
def review_cli(tmp_path, monkeypatch):
    cli = tmp_path / "bin" / "maestri"
    cli.parent.mkdir()
    cli.write_text(REVIEW_CLI)
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("MAESTRI_CLI", str(cli))
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("FAKE_MODE", "active")
    return log


def review(*args, repo):
    return subprocess.run(
        ["python3", str(PROCESS / "review.py"), *args, "--repo", str(repo)],
        capture_output=True,
        text=True,
        env=os.environ,
    )


def request(repo, rng, wait="0"):
    return review("request", rng, "Gauge", "--wait", wait, repo=repo)


def verdict(repo, rng, v, findings=None):
    extra = ["--findings", str(findings)] if findings else []
    return review("verdict", rng, v, *extra, repo=repo)


def test_a_reply_marker_means_the_review_started(review_cli, tmp_path):
    a, b, *_ = _repo(tmp_path)
    p = request(tmp_path, f"{a}..{b}")
    assert p.returncode == 0, p.stderr
    record = json.loads(
        next((tmp_path / ".process" / "reviews").glob("*.json")).read_text()
    )
    assert record["state"] == "requested" and record["from"] == a and record["to"] == b


def test_a_request_that_never_leaves_the_input_box_raises_the_alert_and_can_be_sent_again(
    review_cli, tmp_path, monkeypatch
):
    a, b, *_ = _repo(tmp_path)
    monkeypatch.setenv("FAKE_MODE", "stuckforever")
    p = request(tmp_path, f"{a}..{b}")
    assert p.returncode == 1 and "ALERT" in p.stderr
    assert any(
        "--raw" in line for line in review_cli.read_text().splitlines()
    )  # one Enter was tried first
    monkeypatch.setenv("FAKE_MODE", "active")
    again = request(tmp_path, f"{a}..{b}")  # M2: the same range is re-sent, not refused
    assert again.returncode == 0, again.stderr
    assert len(list((tmp_path / ".process" / "reviews").glob("*.json"))) == 1


def test_an_older_request_in_the_scrollback_is_not_this_request(
    review_cli, tmp_path, monkeypatch
):
    """N3: the stuck check matches this request's unique token, not the start of its text."""
    a, b, *_ = _repo(tmp_path)
    monkeypatch.setenv("FAKE_MODE", "oldtoken")
    assert request(tmp_path, f"{a}..{b}").returncode == 0
    assert not any("--raw" in line for line in review_cli.read_text().splitlines())


def test_an_agent_that_is_already_busy_counts_as_started(
    review_cli, tmp_path, monkeypatch
):
    """The ask queues behind the current work, so no fresh reply marker appears; 'esc to interrupt' means busy."""
    a, b, *_ = _repo(tmp_path)
    monkeypatch.setenv("FAKE_MODE", "busy")
    p = request(tmp_path, f"{a}..{b}")
    assert p.returncode == 0, p.stderr
    assert not any("--raw" in line for line in review_cli.read_text().splitlines())


def test_a_request_stuck_in_the_input_box_is_submitted(
    review_cli, tmp_path, monkeypatch
):
    a, b, *_ = _repo(tmp_path)
    monkeypatch.setenv("FAKE_MODE", "stuck")
    p = request(tmp_path, f"{a}..{b}")
    assert p.returncode == 0, p.stderr
    assert any("--raw" in line for line in review_cli.read_text().splitlines())


def test_an_idle_screen_without_the_request_is_not_an_alarm(
    review_cli, tmp_path, monkeypatch
):
    a, b, *_ = _repo(tmp_path)
    monkeypatch.setenv("FAKE_MODE", "idle")
    assert request(tmp_path, f"{a}..{b}").returncode == 0


def test_a_reviewer_not_connected_to_the_requester_gets_it_through_the_maestro(
    review_cli, tmp_path, monkeypatch
):
    a, b, *_ = _repo(tmp_path)
    monkeypatch.setenv("FAKE_UNCONNECTED", "Gauge Socket")
    monkeypatch.setenv(
        "FAKE_MODE", "stuckforever"
    )  # never consulted: a relayed ask has no screen to watch
    p = review(
        "request",
        f"{a}..{b}",
        "Gauge",
        "--requester",
        "Socket",
        "--wait",
        "0",
        repo=tmp_path,
    )
    assert p.returncode == 0, p.stderr
    assert "through the Maestro" in p.stdout
    calls = review_cli.read_text().splitlines()
    assert any(c.startswith("ask Claude Code RELAY to Gauge") for c in calls)
    assert not any("--raw" in c for c in calls)
    v = verdict(tmp_path, f"{a}..{b}", "APPROVE")
    assert v.returncode == 0 and "through the Maestro" in v.stdout
    assert any(
        c.startswith("ask Claude Code RELAY to Socket")
        for c in review_cli.read_text().splitlines()
    )


def test_changes_then_re_review_restarts_at_the_last_approve_and_lands(
    review_cli, tmp_path
):
    """H2: APPROVE base..c1, CHANGES c1..c2, then c1..c3 is accepted and its APPROVE completes the chain."""
    base, c1, c2, c3 = _repo(tmp_path)
    findings = tmp_path / "f.txt"
    findings.write_text("M1 something")
    assert request(tmp_path, f"{base}..{c1}").returncode == 0
    assert verdict(tmp_path, f"{base}..{c1}", "APPROVE").returncode == 0
    assert request(tmp_path, f"{c1}..{c2}").returncode == 0
    assert verdict(tmp_path, f"{c1}..{c2}", "CHANGES", findings).returncode == 0
    assert (
        "must start at" in request(tmp_path, f"{c2}..{c3}").stderr
    )  # a delta from the CHANGES end is refused
    ok = request(tmp_path, f"{c1}..{c3}")
    assert ok.returncode == 0, ok.stderr
    assert verdict(tmp_path, f"{c1}..{c3}", "APPROVE").returncode == 0
    preflight = load_process_module("land_preflight")
    assert preflight.check_reviews(tmp_path, base, c3) == []


def test_parallel_stories_chain_from_a_request_in_flight(review_cli, tmp_path):
    base, c1, c2, _ = _repo(tmp_path)
    assert request(tmp_path, f"{base}..{c1}").returncode == 0
    assert (
        request(tmp_path, f"{c1}..{c2}").returncode == 0
    )  # story 2 starts where story 1's request ends


def test_first_range_must_start_at_the_merge_base(review_cli, tmp_path):
    base, c1, c2, _ = _repo(tmp_path)
    assert "must start at" in request(tmp_path, f"{c1}..{c2}").stderr


def test_a_changes_verdict_needs_findings_and_a_request(review_cli, tmp_path):
    a, b, *_ = _repo(tmp_path)
    assert "no review request" in verdict(tmp_path, f"{a}..{b}", "APPROVE").stderr
    assert request(tmp_path, f"{a}..{b}").returncode == 0
    assert verdict(tmp_path, f"{a}..{b}", "CHANGES").returncode == 1
    findings = tmp_path / "f.txt"
    findings.write_text("M1 something")
    assert verdict(tmp_path, f"{a}..{b}", "CHANGES", findings).returncode == 0
    assert any("M1 something" in line for line in review_cli.read_text().splitlines())


def test_stop_gate_blocks_undelivered_verdict_once(tmp_path):
    _repo(tmp_path)
    reviews = tmp_path / ".process" / "reviews"
    reviews.mkdir(parents=True)
    (reviews / "a..b.json").write_text(
        json.dumps({"state": "requested", "reviewer": "Gauge"})
    )
    env = {"MAESTRI_TERMINAL_ID": "T", "ZE_ROLE": "review", "ZE_AGENT": "Gauge"}
    assert "no verdict record" in stop_gate.decide({"cwd": str(tmp_path)}, env)
    assert stop_gate.decide({"cwd": str(tmp_path), "stop_hook_active": True}, env) == ""
    assert stop_gate.decide({"cwd": str(tmp_path)}, {"ZE_ROLE": "review"}) == ""
    # L4: a request addressed to another reviewer does not block this one
    assert (
        stop_gate.decide({"cwd": str(tmp_path)}, {**env, "ZE_AGENT": "Caliper"}) == ""
    )
    (reviews / "a..b.json").write_text(
        json.dumps({"state": "delivered", "reviewer": "Gauge"})
    )
    assert stop_gate.decide({"cwd": str(tmp_path)}, env) == ""


def test_state_file_is_stale_only_against_the_agents_own_commit(tmp_path):
    _repo(tmp_path)
    state = tmp_path / "journal" / "state"
    state.mkdir(parents=True)
    file = state / "T.md"
    file.write_text("x")
    env = {"MAESTRI_TERMINAL_ID": "T", "ZE_ROLE": "eng"}
    old = time.time() - 3600
    os.utime(file, (old, old))
    # M1: a teammate's commit (no own-commit stamp for T) never makes T's state file stale
    assert stop_gate.decide({"cwd": str(tmp_path)}, env) == ""
    stamp = tmp_path / ".process" / "own-commit-T"
    stamp.parent.mkdir()
    stamp.write_text("1")
    assert "state file" in stop_gate.decide({"cwd": str(tmp_path)}, env)
    os.utime(file, None)
    assert stop_gate.decide({"cwd": str(tmp_path)}, env) == ""


@pytest.mark.parametrize("role", ["review", "ground-review", "qa", "maestro"])
def test_roles_that_do_not_commit_are_never_nagged_about_the_state_file(tmp_path, role):
    _repo(tmp_path)
    (tmp_path / "journal" / "state").mkdir(parents=True)
    file = tmp_path / "journal" / "state" / "T.md"
    file.write_text("x")
    os.utime(file, (1, 1))
    (tmp_path / ".process").mkdir()
    (tmp_path / ".process" / "own-commit-T").write_text("1")
    assert (
        stop_gate.decide(
            {"cwd": str(tmp_path)}, {"MAESTRI_TERMINAL_ID": "T", "ZE_ROLE": role}
        )
        == ""
    )
