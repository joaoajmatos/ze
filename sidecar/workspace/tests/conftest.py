from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

import main
import scripts
import supervisor


@pytest.fixture
def sidecar(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(supervisor, "WORKSPACE_ROOT", root)
    monkeypatch.setattr(main, "WORKSPACE_ROOT", root)
    monkeypatch.setattr(supervisor, "journal", supervisor.RunJournal())
    monkeypatch.setattr(main, "API_TOKEN", "")
    # Background run tasks (asyncio.create_task in spawn_run) must outlive a
    # single request's portal — keep the TestClient's event loop open for the
    # whole test via the context manager form. Leaving the context runs the
    # app lifespan's shutdown, which cancels a run a test left behind and
    # awaits every _execute task, so no child process outlives the loop that
    # owns its transport ("Event loop is closed" from
    # BaseSubprocessTransport.__del__).
    with TestClient(main.app) as client:
        yield client


def pytest_configure(config):
    config.addinivalue_line("markers", "docker: needs the running workspace container")


@pytest.fixture
def scripts_client(sidecar, request, monkeypatch):
    # Outside pytest's 0700 tmp tree, so the script user can reach its scratch dir as root.
    scratch_root = Path(tempfile.mkdtemp(prefix="ze-scripts-test-"))
    scratch_root.chmod(0o711)
    request.addfinalizer(lambda: shutil.rmtree(scratch_root, ignore_errors=True))
    monkeypatch.setattr(scripts, "SCRATCH_ROOT", scratch_root)
    monkeypatch.setattr(main, "API_TOKEN", "tok")
    monkeypatch.setenv("ZE_SCRIPTS_ALLOW_UNISOLATED", "1")
    monkeypatch.setattr(scripts, "slot", scripts.ScriptSlot())
    monkeypatch.setattr(
        scripts, "isolation", scripts.Isolation(rule_verified=True, mode_set=True)
    )
    sidecar.scratch_root = scratch_root
    return sidecar
