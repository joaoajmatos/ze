"""Contract tests for GET /api/v0/workspace/runs/{id}/events (Phase 129, User
Story 2) — exercises the FastAPI route layer against a fake WorkspaceClient."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ze_api.api import dependencies
from ze_api.api.routes import workspace as workspace_route
from ze_workspace.types import JournalEventDTO, WorkspaceRunStatusDTO


class FakeClient:
    def __init__(self, *, status, events) -> None:
        self._status = status
        self._events = events

    async def get_run(self, run_id):
        return self._status

    async def watch_run(self, run_id):
        for ev in self._events:
            yield ev


def _status() -> WorkspaceRunStatusDTO:
    return WorkspaceRunStatusDTO(
        id=uuid4(),
        status="succeeded",
        exit_code=0,
        timed_out=False,
        stdout_preview="hi",
        stderr_preview="",
        output_file_path=None,
        files_touched=[],
    )


@pytest.fixture
def app_and_client():
    def _build(client):
        app = FastAPI()
        app.state.container = SimpleNamespace(workspace_client=client)
        app.include_router(workspace_route.router, prefix="/api/v0")
        app.dependency_overrides[dependencies.require_api_key] = lambda: None
        return TestClient(app)

    return _build


def test_events_stream_already_terminal_replays_full_buffer(app_and_client):
    run_id = uuid4()
    events = [
        JournalEventDTO(seq=0, type="stdout", data="hi\n"),
        JournalEventDTO(seq=1, type="exit", data="", exit_code=0, timed_out=False),
    ]
    client = FakeClient(status=_status(), events=events)
    test_client = app_and_client(client)

    resp = test_client.get(f"/api/v0/workspace/runs/{run_id}/events")

    assert resp.status_code == 200
    lines = [json.loads(line) for line in resp.text.strip().splitlines() if line]
    assert lines[0] == {"seq": 0, "type": "stdout", "data": "hi\n"}
    assert lines[-1]["type"] == "exit"
    assert lines[-1]["exit_code"] == 0


def test_events_unknown_run_returns_404(app_and_client):
    client = FakeClient(status=None, events=[])
    test_client = app_and_client(client)

    resp = test_client.get(f"/api/v0/workspace/runs/{uuid4()}/events")

    assert resp.status_code == 404


def test_events_two_watchers_both_get_full_replay(app_and_client):
    """Edge Case: both MAY read the same handle — a thin proxy naturally
    supports this since each connection re-invokes client.watch_run()."""
    run_id = uuid4()
    events = [JournalEventDTO(seq=0, type="exit", data="", exit_code=0, timed_out=False)]
    client = FakeClient(status=_status(), events=events)
    test_client = app_and_client(client)

    first = test_client.get(f"/api/v0/workspace/runs/{run_id}/events").text
    second = test_client.get(f"/api/v0/workspace/runs/{run_id}/events").text
    assert first == second


def test_events_stream_redacts_denylisted_key_in_stdout_and_stderr(app_and_client):
    """Phase 131 FR-006: shown live output MUST pass the same redaction as the
    terminal preview — the raw sidecar journal is unredacted, so the /events
    proxy itself MUST redact stdout/stderr data before it reaches the wire."""
    run_id = uuid4()
    events = [
        JournalEventDTO(
            seq=0, type="stdout", data="OPENROUTER_API_KEY=sk-or-fake123\n"
        ),
        JournalEventDTO(seq=1, type="stderr", data="ZE_API_KEY: super-secret\n"),
        JournalEventDTO(seq=2, type="exit", data="", exit_code=0, timed_out=False),
    ]
    client = FakeClient(status=_status(), events=events)
    test_client = app_and_client(client)

    resp = test_client.get(f"/api/v0/workspace/runs/{run_id}/events")

    lines = [json.loads(line) for line in resp.text.strip().splitlines() if line]
    assert "sk-or-fake123" not in lines[0]["data"]
    assert "[redacted]" in lines[0]["data"]
    assert "super-secret" not in lines[1]["data"]
    assert "[redacted]" in lines[1]["data"]


def test_events_stream_does_not_redact_exit_line(app_and_client):
    """exit events carry no free text — redact() must not be applied there."""
    run_id = uuid4()
    events = [JournalEventDTO(seq=0, type="exit", data="", exit_code=1, timed_out=False)]
    client = FakeClient(status=_status(), events=events)
    test_client = app_and_client(client)

    resp = test_client.get(f"/api/v0/workspace/runs/{run_id}/events")

    lines = [json.loads(line) for line in resp.text.strip().splitlines() if line]
    assert lines[0] == {
        "seq": 0,
        "type": "exit",
        "data": "",
        "exit_code": 1,
        "timed_out": False,
    }
