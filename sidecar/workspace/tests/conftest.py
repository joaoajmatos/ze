from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

import main
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
