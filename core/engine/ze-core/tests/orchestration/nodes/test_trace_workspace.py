"""Tests for workspace-run trace extraction (phase 116, User Story 1)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ze_core.orchestration.nodes.trace import _extract_workspace


def _call(tool_name: str, result: str, success: bool = True, args: dict | None = None):
    return SimpleNamespace(
        tool_name=tool_name, args=args or {}, result=result, error="", success=success
    )


@pytest.mark.parametrize(
    "result,expected_status",
    [
        ("[still running] run abc123: `sleep 60` is taking longer than 25s...", "in_progress"),
        ("ok\n(exit 0)", None),
    ],
)
async def test_extract_workspace_projects_in_progress_only_for_still_running(
    result, expected_status
):
    agent_result = SimpleNamespace(
        tool_calls=[_call("workspace_run", result, args={"command": "sleep 60"})]
    )
    trace = await _extract_workspace(agent_result, config={})
    assert trace is not None
    assert len(trace.runs) == 1
    assert trace.runs[0].get("status") == expected_status


async def test_extract_workspace_still_running_extracts_run_id():
    """Phase 131 FR-001/002: the chat live-output view needs the handle, which
    the tool reply already embeds ('run <id>:') but the trace never surfaced."""
    agent_result = SimpleNamespace(
        tool_calls=[
            _call(
                "workspace_run",
                "[still running] run 8f14e45f-ceea-4b19-9b8e-3f9b5c1e2a3d: "
                "`sleep 60` is taking longer than 25s and is continuing in "
                "the background. I'll follow up on this thread once it finishes.",
                args={"command": "sleep 60"},
            )
        ]
    )
    trace = await _extract_workspace(agent_result, config={})
    assert trace.runs[0]["id"] == "8f14e45f-ceea-4b19-9b8e-3f9b5c1e2a3d"


async def test_extract_workspace_terminal_run_has_no_id():
    agent_result = SimpleNamespace(
        tool_calls=[_call("workspace_run", "ok\n(exit 0)", args={"command": "echo ok"})]
    )
    trace = await _extract_workspace(agent_result, config={})
    assert "id" not in trace.runs[0]


async def test_extract_workspace_in_progress_never_touches_workspace_run_status():
    agent_result = SimpleNamespace(
        tool_calls=[
            _call(
                "workspace_run",
                "[still running] run abc123: `sleep 60`...",
                args={"command": "sleep 60"},
            )
        ]
    )
    trace = await _extract_workspace(agent_result, config={})
    # Trace-only projection: no workspace_runs.status write happens here — this
    # extractor only ever reads tool-call results, never a store.
    assert trace.runs[0]["status"] == "in_progress"
    assert trace.runs[0]["command"] == "sleep 60"
