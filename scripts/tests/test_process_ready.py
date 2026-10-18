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
