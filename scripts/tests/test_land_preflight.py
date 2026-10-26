import json
import subprocess

import pytest
from conftest import PROCESS, load_process_module

preflight = load_process_module("land_preflight")
phase_status = load_process_module("check_phase_status")


def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


@pytest.fixture
def world(tmp_path):
    ground = tmp_path / "ground"
    ground.mkdir()
    git(ground, "init", "-q", "-b", "main")
    git(ground, "config", "user.email", "a@b")
    git(ground, "config", "user.name", "t")
    (ground / "Makefile").write_text("lint:\n\t@true\n")
    (ground / "AGENTS.md").write_text("| 200 | Thing | Implemented |\n")
    (ground / "specs").mkdir()
    (ground / "specs" / "README.md").write_text(
        "| 200 | [Thing](phases/200-thing/spec.md) | ✅ Implemented |\n"
    )
    (ground / "specs" / "phases").mkdir()
    git(ground, "add", "-A")
    git(ground, "commit", "-q", "-m", "base")
    floor = tmp_path / "floor"
    git(ground, "worktree", "add", "-q", "-b", "feat", str(floor))
    (floor / "x.py").write_text("x = 1\n")
    git(floor, "add", "x.py")
    git(floor, "commit", "-q", "-m", "work")
    return ground, floor


def make_receipt(floor, gates=({"gate": "lint", "rc": 0},), dirty=0):
    sha = git(floor, "rev-parse", "HEAD")
    path = floor / ".process" / "receipts" / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"sha": sha, "dirty_files": dirty, "gates": list(gates)})
    )


def make_review(floor, start, end, verdict="APPROVE", name=None):
    path = floor / ".process" / "reviews" / f"{name or start[:8]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"from": start, "to": end, "verdict": verdict}))


def run(floor):
    return subprocess.run(
        [str(PROCESS / "land_preflight.py"), "--floor", str(floor)],
        capture_output=True,
        text=True,
    )


def ready_floor(floor):
    make_receipt(floor)
    make_review(
        floor, git(floor, "merge-base", "HEAD", "main"), git(floor, "rev-parse", "HEAD")
    )


def test_happy_path(world):
    _, floor = world
    (floor / ".gitignore").write_text(".process/\n")
    git(floor, "add", ".gitignore")
    git(floor, "commit", "-q", "-m", "ignore")
    ready_floor(floor)
    p = run(floor)
    assert p.returncode == 0, p.stdout
    assert "ok" in p.stdout


def test_missing_receipt_and_review_are_named(world):
    _, floor = world
    out = run(floor).stdout
    assert "no gate receipt for HEAD" in out
    assert "no APPROVE review record" in out


def test_failed_gate_dirty_receipt_and_missing_gate(world):
    _, floor = world
    make_receipt(floor, gates=({"gate": "lint", "rc": 1},), dirty=2)
    out = "\n".join(
        preflight.check_receipt(
            floor,
            git(floor, "merge-base", "HEAD", "main"),
            git(floor, "rev-parse", "HEAD"),
        )
    )
    assert "failing gates: lint" in out and "uncommitted" in out
    make_receipt(floor, gates=({"gate": "other", "rc": 0},))
    out = "\n".join(
        preflight.check_receipt(
            floor,
            git(floor, "merge-base", "HEAD", "main"),
            git(floor, "rev-parse", "HEAD"),
        )
    )
    assert "lacks gates the diff needs: lint" in out


def test_changes_verdict_does_not_count_and_chain_must_reach_head(world):
    _, floor = world
    base, head = (
        git(floor, "merge-base", "HEAD", "main"),
        git(floor, "rev-parse", "HEAD"),
    )
    make_review(floor, base, head, verdict="CHANGES")
    assert preflight.check_reviews(floor, base, head)
    (floor / "y.py").write_text("y = 1\n")
    git(floor, "add", "y.py")
    git(floor, "commit", "-q", "-m", "more")
    head2 = git(floor, "rev-parse", "HEAD")
    make_review(floor, base, head, name="one")
    assert preflight.check_reviews(floor, base, head2)
    make_review(floor, head, head2, name="two")
    assert preflight.check_reviews(floor, base, head2) == []


def test_untracked_in_floor_and_ground(world):
    ground, floor = world
    (floor / "stray.txt").write_text("x")
    (ground / "other.txt").write_text("x")
    out = "\n".join(preflight.check_untracked(floor, ground))
    assert "untracked in floor: stray.txt" in out
    assert "untracked in Ground: other.txt" in out


def test_merge_conflict_is_reported(world):
    ground, floor = world
    (floor / "same.txt").write_text("floor\n")
    git(floor, "add", "same.txt")
    git(floor, "commit", "-q", "-m", "f")
    (ground / "same.txt").write_text("ground\n")
    git(ground, "add", "same.txt")
    git(ground, "commit", "-q", "-m", "g")
    out = "\n".join(preflight.check_history(floor, "main"))
    assert "conflicts" in out and "same.txt" in out


def test_new_arch_file(world):
    _, floor = world
    (floor / "specs" / "arch").mkdir()
    (floor / "specs" / "arch" / "notes.md").write_text("x")
    git(floor, "add", "-A")
    git(floor, "commit", "-q", "-m", "arch")
    base = git(floor, "merge-base", "HEAD", "main")
    assert preflight.check_arch(floor, base) == [
        "new file under specs/arch/: specs/arch/notes.md"
    ]


def test_dry_run_lists_every_check(world):
    _, floor = world
    p = subprocess.run(
        [str(PROCESS / "land_preflight.py"), "--floor", str(floor), "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0 and p.stdout.count("\n") == len(preflight.CHECKS) + 1


def _phase(root, spec_status, tasks, agents="Implemented", readme="✅ Implemented"):
    d = root / "specs" / "phases" / "200-thing"
    d.mkdir(parents=True, exist_ok=True)
    (d / "spec.md").write_text(f"# Thing\n\n**Status**: {spec_status}\n")
    (d / "tasks.md").write_text(tasks)
    return (
        d,
        f"| 200 | Thing | {agents} |\n",
        f"| 200 | [Thing](phases/200-thing/spec.md) | {readme} |\n",
    )


@pytest.mark.parametrize(
    ("spec", "tasks", "agents", "readme", "expect"),
    [
        ("Implemented", "- [x] T001 a\n", "Implemented", "✅ Implemented", []),
        (
            "Ready to implement",
            "- [x] T001 a\n",
            "Implemented",
            "✅ Implemented",
            "spec.md Status",
        ),
        ("Implemented", "- [x] T001 a\n", "Planned", "✅ Implemented", "AGENTS.md row"),
        (
            "Implemented",
            "- [x] T001 a\n",
            "Implemented",
            "Draft",
            "specs/README.md row",
        ),
        (
            "Implemented",
            "- [x] T001 a\n- [ ] T002 b\n",
            "Implemented",
            "✅ Implemented",
            "open tasks",
        ),
        ("Draft", "- [x] T001 a\n- [ ] T002 b\n", "Planned", "Draft", []),
        ("Implemented (note)", "", "Implemented", "✅ Implemented", []),
    ],
)
def test_phase_status(tmp_path, spec, tasks, agents, readme, expect):
    d, agents_text, readme_text = _phase(tmp_path, spec, tasks, agents, readme)
    errs = phase_status.check(d, agents_text, readme_text)
    if expect:
        assert any(expect in e for e in errs), errs
    else:
        assert errs == []


def test_phase_without_agents_row_is_reported(tmp_path):
    d, _, readme = _phase(tmp_path, "Implemented", "- [x] T001 a\n")
    assert any("no phase row" in e for e in phase_status.check(d, "", readme))


def test_floor_check_detects_old_fork(world):
    ground, floor = world
    script = str(PROCESS / "floor_check.sh")
    assert subprocess.run([script], cwd=floor, capture_output=True).returncode == 0
    (ground / "new.txt").write_text("x")
    git(ground, "add", "new.txt")
    git(ground, "commit", "-q", "-m", "advance")
    p = subprocess.run([script], cwd=floor, capture_output=True, text=True)
    assert p.returncode == 1 and "old commit" in p.stderr


def test_land_post_dry_run_changes_nothing(world):
    ground, _ = world
    before = git(ground, "status", "--porcelain")
    p = subprocess.run(
        [str(PROCESS / "land_post.sh"), "--dry-run"],
        cwd=ground,
        capture_output=True,
        text=True,
    )
    assert "== graph" in p.stdout and "== push main" in p.stdout
    assert git(ground, "status", "--porcelain") == before


def test_land_post_rejects_an_empty_or_partial_receipt(world):
    """H1: a receipt with no gates (or only some) must not let main be pushed."""
    ground, _ = world
    sha = git(ground, "rev-parse", "HEAD")
    receipts = ground / ".process" / "receipts"
    receipts.mkdir(parents=True)

    def run_post(gates):
        (receipts / f"{sha}.json").write_text(
            json.dumps({"sha": sha, "dirty_files": 0, "gates": gates})
        )
        return subprocess.run(
            [str(PROCESS / "land_post.sh"), "--dry-run"],
            cwd=ground,
            capture_output=True,
            text=True,
        )

    assert "not green" in run_post([]).stderr
    assert "missing=" in run_post([{"gate": "lint", "rc": 0}]).stderr
    full = [
        {"gate": g, "rc": 0}
        for g in ("lint", "test-py", "test-web", "typecheck-web", "lint-web")
    ]
    assert "not green" not in run_post(full).stderr


def test_ok_archives_floor_and_lane_records_to_ground(world, tmp_path):
    ground, floor = world
    (floor / ".gitignore").write_text(".process/\n")
    git(floor, "add", ".gitignore")
    git(floor, "commit", "-q", "-m", "ignore")
    ready_floor(floor)
    lane = tmp_path / "lane"
    git(ground, "worktree", "add", "-q", "-b", "feat-lane-x", str(lane), "feat")
    make_review(lane, "a" * 40, "b" * 40, verdict="CHANGES", name="lane-round")
    p = run(floor)
    assert p.returncode == 0, p.stdout
    dest = ground / "journal" / "metrics" / "feat"
    reviews = sorted(f.name for f in (dest / "reviews").glob("*.json"))
    assert "lane-round.json" in reviews and len(reviews) == 2
    assert len(list((dest / "receipts").glob("*.json"))) == 1


def test_failed_preflight_archives_nothing(world):
    ground, floor = world
    p = run(floor)
    assert p.returncode == 1
    assert not (ground / "journal" / "metrics").exists()
