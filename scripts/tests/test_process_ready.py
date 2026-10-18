import json
import subprocess
from pathlib import Path

from conftest import PROCESS, load_process_module

REPO = Path(__file__).parents[2]
ready = load_process_module("ready")
check_query_errors = load_process_module("check_query_errors")


def test_targets_are_read_from_the_makefile():
    targets = ready.test_targets((REPO / "Makefile").read_text())
    assert targets["apps/ze-api"] == "test-api"
    assert targets["core/engine/ze-core"] == "test-core"
    assert targets["plugins/ze-calendar"] == "test-calendar"


def test_gate_selection():
    targets = {"core/engine/ze-core": "test-core", "scripts": "test-scripts"}
    assert ready.select_gates(["core/engine/ze-core/ze_core/a.py"], targets) == [
        "lint",
        "test-core",
    ]
    assert ready.select_gates(["apps/ze-web/src/a.ts"], targets) == [
        "typecheck-web",
        "lint-web",
        "test-web",
    ]
    assert ready.select_gates(["docs/x.md"], targets) == []
    assert ready.select_gates(["scripts/process/a.py"], targets) == [
        "lint",
        "test-scripts",
    ]


def test_old_route_literals(tmp_path, monkeypatch):
    places = tmp_path / "apps/ze-web/src/shared/config/places.ts"
    places.parent.mkdir(parents=True)
    places.write_text('{ from: "/goals", to: "/doing/goals" },')
    page = tmp_path / "apps/ze-web/src/pages/a.tsx"
    page.parent.mkdir(parents=True)
    page.write_text('navigate("/goals")')
    monkeypatch.chdir(tmp_path)
    assert len(ready.old_route_hits(["apps/ze-web/src/pages/a.tsx"])) == 1
    page.write_text('navigate("/doing/goals")')
    assert ready.old_route_hits(["apps/ze-web/src/pages/a.tsx"]) == []


def test_query_errors(tmp_path, monkeypatch):
    web = tmp_path / "apps/ze-web/src/entities/thing/api"
    web.mkdir(parents=True)
    good = web / "useThingQuery.ts"
    good.write_text("export function useThingQuery() { if (error) throw error; }")
    bad = web / "useOtherQuery.ts"
    bad.write_text("export function useOtherQuery() { return data ?? []; }")
    (tmp_path / "apps/ze-web/src/a.test.tsx").write_text("useThingQuery isError")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(check_query_errors, "WEB_SRC", Path("apps/ze-web/src"))
    assert check_query_errors.check([str(good.relative_to(tmp_path))]) == []
    errs = check_query_errors.check([str(bad.relative_to(tmp_path))])
    assert len(errs) == 2
    assert check_query_errors.check(["apps/ze-web/src/other.ts"]) == []


def _repo_with_gates(tmp_path: Path) -> Path:
    for args in (
        ["init", "-q"],
        ["config", "user.email", "a@b"],
        ["config", "user.name", "t"],
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    (tmp_path / "Makefile").write_text("good:\n\t@true\nbad:\n\t@echo boom; exit 3\n")
    subprocess.run(["git", "add", "Makefile"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "i"], cwd=tmp_path, check=True)
    return tmp_path


def test_gates_receipt_records_each_rc(tmp_path):
    repo = _repo_with_gates(tmp_path)
    p = subprocess.run(
        [str(PROCESS / "gates.sh"), "-", "good", "bad"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert p.returncode == 1
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    receipt = json.loads((repo / ".process" / "receipts" / f"{sha}.json").read_text())
    assert receipt["sha"] == sha
    assert {g["gate"]: g["rc"] for g in receipt["gates"]} == {"good": 0, "bad": 2}
    assert "boom" in Path(receipt["gates"][1]["log"]).read_text()


def test_gates_all_green_exits_zero(tmp_path):
    repo = _repo_with_gates(tmp_path)
    assert (
        subprocess.run(
            [str(PROCESS / "gates.sh"), "-", "good"], cwd=repo, capture_output=True
        ).returncode
        == 0
    )


def _heavy_repo(tmp_path: Path) -> Path:
    repo = _repo_with_gates(tmp_path)
    (repo / "Makefile").write_text("test-py:\n\t@true\nlint:\n\t@true\n")
    return repo


def test_full_gate_waits_for_a_live_lock_and_cleans_a_stale_one(tmp_path):
    import os

    repo = _heavy_repo(tmp_path)
    lock = tmp_path / "gate.lock"
    env = {**os.environ, "ZE_GATE_LOCK": str(lock), "ZE_GATE_LOCK_POLL": "0.2"}
    # stale: holder pid does not exist
    lock.mkdir()
    (lock / "pid").write_text("999999")
    p = subprocess.run(
        [str(PROCESS / "gates.sh"), "-", "test-py"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert p.returncode == 0 and not lock.exists()
    # live holder: a sleeping process; the gate must wait until it exits
    import threading

    holder = subprocess.Popen(["sleep", "2"])
    threading.Thread(
        target=holder.wait, daemon=True
    ).start()  # reap it, or kill -0 still sees a zombie
    lock.mkdir()
    (lock / "pid").write_text(str(holder.pid))
    p = subprocess.run(
        [str(PROCESS / "gates.sh"), "-", "test-py"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert (
        "waiting for the full-gate lock" in p.stderr
        and p.returncode == 0
        and not lock.exists()
    )


def test_light_gates_ignore_the_lock(tmp_path):
    import os

    repo = _heavy_repo(tmp_path)
    lock = tmp_path / "gate.lock"
    lock.mkdir()
    (lock / "pid").write_text(str(os.getpid()))
    env = {**os.environ, "ZE_GATE_LOCK": str(lock)}
    p = subprocess.run(
        [str(PROCESS / "gates.sh"), "-", "lint"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert p.returncode == 0 and lock.exists()


def test_gates_under_gate_lock_do_not_deadlock(tmp_path):
    import os

    repo = _heavy_repo(tmp_path)
    lock = tmp_path / "gate.lock"
    env = {**os.environ, "ZE_GATE_LOCK": str(lock)}
    wrapper = (
        f"mkdir {lock} && echo $$ > {lock}/pid && exec {PROCESS / 'gates.sh'} - test-py"
    )
    p = subprocess.run(
        ["sh", "-c", wrapper],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert p.returncode == 0


def _main_with_makefile(tmp_path: Path) -> Path:
    repo = _repo_with_gates(tmp_path)
    subprocess.run(["git", "branch", "-m", "main"], cwd=repo, check=True)
    (repo / "Makefile").write_text(
        "test-core:\n\t$(call pytest_pkg,core/engine/ze-core/tests)\n"
    )
    subprocess.run(["git", "commit", "-qam", "m"], cwd=repo, check=True)
    return repo


def test_land_profile_runs_every_gate_even_when_the_diff_is_empty(tmp_path):
    """H1: on Ground after a land the diff against main is empty; the land profile still selects every gate."""
    repo = _main_with_makefile(tmp_path)
    p = subprocess.run(
        ["python3", str(PROCESS / "ready.py"), "--dry-run", "--profile", "land"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert "0 changed file(s)" in p.stdout
    assert f"gates: {' '.join(ready.LAND_GATES)}" in p.stdout
    plain = subprocess.run(
        ["python3", str(PROCESS / "ready.py"), "--dry-run"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert "gates: (none)" in plain.stdout


def test_an_untracked_new_file_selects_gates_and_makes_the_receipt_dirty(
    tmp_path, monkeypatch
):
    """L2: a new, uncommitted .py file must not slip past the gate selection or the dirty count."""
    repo = _main_with_makefile(tmp_path)
    (repo / "core" / "engine" / "ze-core").mkdir(parents=True)
    (repo / "core" / "engine" / "ze-core" / "new.py").write_text("x = 1\n")
    monkeypatch.chdir(repo)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    assert "core/engine/ze-core/new.py" in ready.changed_files(base)
    targets = ready.test_targets((repo / "Makefile").read_text())
    assert ready.select_gates(ready.changed_files(base), targets) == [
        "lint",
        "test-core",
    ]
    (repo / "Makefile").write_text("lint:\n\t@true\n")
    p = subprocess.run(
        [str(PROCESS / "gates.sh"), "-", "lint"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    sha = base
    receipt = json.loads((repo / ".process" / "receipts" / f"{sha}.json").read_text())
    assert receipt["dirty_files"] >= 1 and p.returncode == 0


def test_dirty_count_ignores_process_files_and_scratchpads_but_not_new_sources(
    tmp_path,
):
    """N2: untracked files block a green receipt, except the receipt's own files and scratchpad paths."""
    repo = _repo_with_gates(tmp_path)
    (repo / ".process").mkdir(exist_ok=True)
    (repo / ".process" / "own-commit-T").write_text("1")
    (repo / "scratchpad").mkdir()
    (repo / "scratchpad" / "notes.md").write_text("x")
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    def dirty():
        subprocess.run(
            [str(PROCESS / "gates.sh"), "-", "good"],
            cwd=repo,
            capture_output=True,
            check=True,
        )
        return json.loads((repo / ".process" / "receipts" / f"{sha}.json").read_text())[
            "dirty_files"
        ]

    assert dirty() == 0
    (repo / "new_module.py").write_text("x = 1\n")
    assert dirty() == 1
