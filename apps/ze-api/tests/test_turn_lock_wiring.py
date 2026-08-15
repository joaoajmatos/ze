"""ThreadTurnLock has exactly one owner: ZeContainer.invoke_raw_turn/resume_turn
(Phase 116, User Story 2, T022/T025). The WebSocket turn handler, the eval
route, and the RunWatcher's TurnStarter adapter must all call the container
methods directly with no ThreadTurnLock acquisition of their own — a second
acquire on the same non-reentrant asyncio.Lock would deadlock.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

import ze_api.api.routes.eval as eval_route
import ze_api.api.websocket.confirmation as confirmation_module
import ze_api.api.websocket.turns as turns_module
import ze_api.container as container_module
from ze_agents.interface.types import RawInput
from ze_workspace.turn_lock import ThreadTurnLock


def test_call_sites_do_not_reference_thread_turn_lock():
    """Source-level guard: none of the three call sites import or touch
    ThreadTurnLock — locking is entirely internal to ZeContainer."""
    for module in (turns_module, eval_route, confirmation_module):
        source = inspect.getsource(module)
        assert "turn_lock" not in source
        assert "ThreadTurnLock" not in source


@pytest.mark.asyncio
async def test_locked_invoke_raw_turn_serializes_same_thread(monkeypatch):
    lock = ThreadTurnLock()
    order: list[str] = []

    async def fake_invoke_raw_turn(container, thread_id, raw, *, config_extra=None):
        order.append(f"start-{raw.text}")
        await asyncio.sleep(0.02)
        order.append(f"end-{raw.text}")
        return None

    monkeypatch.setattr(container_module, "invoke_raw_turn", fake_invoke_raw_turn)

    async def call(text: str):
        return await container_module._locked_invoke_raw_turn(
            None, lock, "same-thread", RawInput(text=text)
        )

    await asyncio.gather(call("a"), call("b"))

    # Must not interleave: one call's start/end must be contiguous.
    assert order in (
        ["start-a", "end-a", "start-b", "end-b"],
        ["start-b", "end-b", "start-a", "end-a"],
    )


@pytest.mark.asyncio
async def test_locked_invoke_raw_turn_does_not_serialize_different_threads(monkeypatch):
    lock = ThreadTurnLock()
    running: list[str] = []
    overlapped = False

    async def fake_invoke_raw_turn(container, thread_id, raw, *, config_extra=None):
        nonlocal overlapped
        running.append(thread_id)
        await asyncio.sleep(0.02)
        if len(running) == 2:
            overlapped = True
        running.remove(thread_id)
        return None

    monkeypatch.setattr(container_module, "invoke_raw_turn", fake_invoke_raw_turn)

    async def call(thread_id: str):
        return await container_module._locked_invoke_raw_turn(
            None, lock, thread_id, RawInput(text="x")
        )

    await asyncio.gather(call("thread-a"), call("thread-b"))
    assert overlapped is True


@pytest.mark.asyncio
async def test_locked_resume_turn_extracts_thread_id_from_config(monkeypatch):
    lock = ThreadTurnLock()
    seen_thread_ids: list[str] = []

    async def fake_resume_turn(container, config, resume=None):
        seen_thread_ids.append(config["configurable"]["thread_id"])
        return None

    monkeypatch.setattr(container_module, "resume_turn", fake_resume_turn)

    await container_module._locked_resume_turn(
        None, lock, {"configurable": {"thread_id": "t9"}}
    )
    assert seen_thread_ids == ["t9"]
    assert "t9" in lock._locks
