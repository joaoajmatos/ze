import json
import subprocess
import sys

import pytest
from conftest import PROCESS, load_hook

HOOK = PROCESS / "hooks" / "guard_edit.py"
module = load_hook("guard_edit")

AGENT = {"MAESTRI_TERMINAL_ID": "T"}


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "specs" / "arch").mkdir(parents=True)
    (tmp_path / "specs" / "arch" / "old.md").write_text("x")
    return tmp_path


def call(repo, tool, path, role="", env=None):
    payload = {
        "tool_name": tool,
        "cwd": str(repo),
        "tool_input": {"file_path": str(path)},
    }
    return module.decide(payload, {**AGENT, "ZE_ROLE": role, **(env or {})})


def test_noop_outside_maestri(repo):
    assert module.decide({"tool_name": "AskUserQuestion"}, {"ZE_ROLE": "eng"}) == ""


@pytest.mark.parametrize(
    ("role", "blocked"),
    [("eng", True), ("review", True), ("maestro", False), ("", False)],
)
def test_ask_user_question(role, blocked):
    assert (
        bool(
            module.decide({"tool_name": "AskUserQuestion"}, {**AGENT, "ZE_ROLE": role})
        )
        is blocked
    )


def test_reviewer_is_read_only_except_scratchpad(repo):
    assert call(repo, "Edit", repo / "a.py", "review")
    assert (
        call(repo, "Write", "/private/tmp/claude-1/x/scratchpad/findings.md", "review")
        == ""
    )
    assert call(repo, "Edit", repo / "a.py", "eng") == ""


def test_receipts_and_reviews_are_not_hand_written(repo):
    assert call(repo, "Write", repo / ".process" / "receipts" / "abc.json", "eng")
    assert call(repo, "Write", repo / ".process" / "reviews" / "a..b.json", "")
    assert call(repo, "Write", repo / ".process" / "other.txt", "eng") == ""


def test_new_arch_file(repo):
    assert call(repo, "Write", repo / "specs" / "arch" / "notes.md", "eng")
    assert call(repo, "Write", repo / "specs" / "arch" / "notes.md", "architect") == ""
    assert call(repo, "Edit", repo / "specs" / "arch" / "old.md", "eng") == ""


def test_lane_globs(repo):
    (repo / ".process").mkdir()
    (repo / ".process" / "lane.json").write_text(
        json.dumps({"lane": "a", "owns": ["apps/ze-web/src/pages/a/*", "docs/a.md"]})
    )
    assert call(repo, "Edit", repo / "apps/ze-web/src/pages/a/Page.tsx", "eng") == ""
    assert call(repo, "Edit", repo / "docs/a.md", "eng") == ""
    reason = call(repo, "Edit", repo / "apps/ze-web/src/app/router.tsx", "eng")
    assert "outside lane a" in reason


def test_exit_contract(repo):
    import os

    env = {**os.environ, **AGENT, "ZE_ROLE": "eng"}
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "AskUserQuestion"}),
        text=True,
        capture_output=True,
        env=env,
    )
    assert p.returncode == 2 and "BLOCKED" in p.stderr
    assert (
        subprocess.run(
            [sys.executable, str(HOOK)], input="junk", text=True, capture_output=True
        ).returncode
        == 0
    )


@pytest.mark.parametrize("role", ["review", "ground-review", "qa", "eng"])
def test_every_role_may_write_its_own_state_file(repo, role):
    """H3: the Stop hook demands a state-file update, so the Edit hook must allow it, reviewers included."""
    own = repo / "journal" / "state" / "T.md"
    assert call(repo, "Edit", own, role) == ""
    other = repo / "journal" / "state" / "OTHER.md"
    assert (call(repo, "Edit", other, role) != "") is (
        role in ("review", "ground-review")
    )


def test_ground_review_is_read_only_like_review(repo):
    assert call(repo, "Edit", repo / "a.py", "ground-review")
