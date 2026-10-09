from __future__ import annotations

import sys
import time
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
    # whole test via the context manager form.
    with TestClient(main.app) as client:
        yield client
        _drain_runs(client)


def _drain_runs(client: TestClient, timeout: float = 10.0) -> None:
    """Cancel any run a test left behind and wait for its terminal status.

    _execute only finishes after proc.wait() and the pipe pumps complete, so a
    terminal status means the subprocess transport is closed. Leaving the
    TestClient with a live child lets the transport be garbage-collected after
    its event loop closed ("Event loop is closed" from BaseSubprocessTransport.__del__).
    """
    deadline = time.monotonic() + timeout
    while (entry := supervisor.journal.running()) is not None:
        client.post(f"/runs/{entry.id}/cancel")
        if time.monotonic() > deadline:
            raise AssertionError(f"run {entry.id} did not reach a terminal status")
        time.sleep(0.02)
