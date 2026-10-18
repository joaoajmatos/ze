"""WorkspaceScriptRunner against the T007 fake sidecar."""

from __future__ import annotations

import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from ze_agents.errors import AgentAbortedError
from ze_agents.scripts import (
    DispatchReply,
    ScriptContext,
    ScriptLimits,
    ScriptOutcome,
    ScriptRequest,
)

from tests.fixtures.script_frames import (
    END_STATUSES,
    WS_MAX_SIZE,
    FakeScriptSidecar,
    WaitForZe,
    call_frame,
    end_frame,
    start_frame,
)
from tests.test_script_learning import FakeLedger
from ze_workspace.client import WorkspaceClient
from ze_workspace.errors import WorkspaceUnavailableError
from ze_workspace.script_learning import ScriptLearning
from ze_workspace.scripts import WorkspaceScriptRunner
from ze_workspace.types import WorkspaceStat


def make_client(*, isolated: bool = True, stat_error: Exception | None = None):
    client = WorkspaceClient("http://sidecar:8080", token="tok")
    stat = WorkspaceStat(
        bytes_used=0, bytes_ceiling=1, busy=False, scripts_isolated=isolated
    )
    client.stat = AsyncMock(side_effect=stat_error, return_value=stat)
    return client


async def ok_dispatch(request: ScriptRequest) -> DispatchReply:
    return DispatchReply(ok=True, value=[request.seq])


def runner_for(sidecar, client=None, **kwargs) -> WorkspaceScriptRunner:
    return WorkspaceScriptRunner(
        client or make_client(), connect=sidecar.connect, **kwargs
    )


async def run(runner, dispatch=ok_dispatch, limits: ScriptLimits | None = None):
    return await runner.run(
        script_id="s1",
        agent="finance",
        source="print(1)",
        stub="# stub",
        limits=limits or ScriptLimits(),
        dispatch=dispatch,
    )


async def test_start_carries_token_and_start_frame():
    sidecar = FakeScriptSidecar([end_frame("ok", value=1)])
    outcome = await run(runner_for(sidecar))
    assert outcome == ScriptOutcome(status="ok", value=1)
    assert sidecar.socket.sent_of("start") == [start_frame("s1", "print(1)", "# stub", 30)]
    connect = sidecar.connects[0]
    assert connect["url"] == "ws://sidecar:8080/scripts"
    assert connect["additional_headers"] == {"Authorization": "Bearer tok"}
    assert connect["max_size"] == WS_MAX_SIZE


async def test_calls_are_dispatched_and_replied_in_order():
    sidecar = FakeScriptSidecar(
        [call_frame(1, "a", {"x": 1}), call_frame(2, "b"), end_frame("ok", value="done")]
    )
    seen: list[ScriptRequest] = []

    async def dispatch(request):
        seen.append(request)
        return DispatchReply(ok=request.tool == "a", value=[1], error="nope")

    outcome = await run(runner_for(sidecar), dispatch)
    assert [r.tool for r in seen] == ["a", "b"]
    assert seen[0].args == {"x": 1}
    replies = sidecar.socket.sent_of("reply")
    assert replies == [
        {"type": "reply", "seq": 1, "ok": True, "value": [1]},
        {"type": "reply", "seq": 2, "ok": False, "error": "nope"},
    ]
    assert outcome.status == "ok"


async def test_stop_reply_sends_cancel_after_the_reply():
    sidecar = FakeScriptSidecar([call_frame(1, "a"), end_frame("killed")])

    async def dispatch(request):
        return DispatchReply(ok=False, error="limit: inner_calls (20)", stop=True)

    outcome = await run(runner_for(sidecar), dispatch)
    types = [f["type"] for f in sidecar.socket.sent]
    assert types == ["start", "reply", "cancel"]
    assert outcome.status == "killed"


@pytest.mark.parametrize("status", END_STATUSES)
async def test_end_maps_to_outcome(status):
    sidecar = FakeScriptSidecar(
        [
            end_frame(
                status,
                value={"k": 1},
                writes=[{"tool": "w", "args": {}}],
                stderr_tail="tail",
                exception="Boom",
            )
        ]
    )
    outcome = await run(runner_for(sidecar))
    assert outcome == ScriptOutcome(
        status=status,
        value={"k": 1},
        writes=[{"tool": "w", "args": {}}],
        stderr_tail="tail",
        exception="Boom",
    )


async def test_connection_refused_is_unavailable():
    def refuse(url, **kwargs):
        raise ConnectionRefusedError("no")

    runner = WorkspaceScriptRunner(make_client(), connect=refuse)
    assert (await run(runner)).status == "unavailable"


async def test_end_busy_is_busy():
    sidecar = FakeScriptSidecar([end_frame("busy")])
    assert (await run(runner_for(sidecar))).status == "busy"


async def test_no_end_in_time_cancels_and_times_out():
    sidecar = FakeScriptSidecar([])
    runner = runner_for(sidecar, grace_seconds=0.05)
    limits = ScriptLimits(wall_seconds=0.05)  # type: ignore[arg-type]
    outcome = await asyncio.wait_for(run(runner, limits=limits), 2)
    assert outcome.status == "timeout"
    assert sidecar.socket.sent_of("cancel") == [{"type": "cancel"}]


async def test_unisolated_sidecar_never_opens_the_socket():
    sidecar = FakeScriptSidecar([end_frame("ok")])
    outcome = await run(runner_for(sidecar, make_client(isolated=False)))
    assert outcome.status == "unavailable"
    assert sidecar.connects == []


async def test_stat_failure_is_unavailable():
    client = make_client(stat_error=WorkspaceUnavailableError("down"))
    sidecar = FakeScriptSidecar([end_frame("ok")])
    outcome = await run(runner_for(sidecar, client))
    assert outcome.status == "unavailable"
    assert sidecar.connects == []


async def test_dispatch_error_replies_not_ok_and_continues():
    sidecar = FakeScriptSidecar([call_frame(1, "a"), end_frame("ok")])

    async def dispatch(request):
        raise RuntimeError("kaput")

    outcome = await run(runner_for(sidecar), dispatch)
    reply = sidecar.socket.sent_of("reply")[0]
    assert reply["ok"] is False and "kaput" in reply["error"]
    assert outcome.status == "ok"


async def test_learning_gets_the_run_without_blocking():
    sidecar = FakeScriptSidecar([call_frame(1, "a"), call_frame(2, "b"), end_frame("ok")])
    learning = AsyncMock()
    runner = runner_for(sidecar, learning=learning)
    await run(runner)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    kwargs = learning.record.await_args.kwargs
    assert kwargs["tools"] == ["a", "b"]
    assert kwargs["agent"] == "finance"
    assert kwargs["outcome"].status == "ok"
    assert kwargs["procedure_id"] is None


async def test_procedure_id_reaches_learning():
    sidecar = FakeScriptSidecar([end_frame("ok")])
    learning = AsyncMock()
    runner = runner_for(sidecar, learning=learning)
    await runner.run(
        script_id="s1", agent="a", source="x", stub="", limits=ScriptLimits(),
        dispatch=ok_dispatch, procedure_id="p-1",
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert learning.record.await_args.kwargs["procedure_id"] == "p-1"


async def test_wait_for_ze_fixture_still_works():
    sidecar = FakeScriptSidecar([WaitForZe("start"), end_frame("ok")])
    assert (await run(runner_for(sidecar))).status == "ok"


async def _drain() -> None:
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not current]
    await asyncio.gather(*pending, return_exceptions=True)


async def test_abort_in_dispatch_propagates_and_cancels():
    sidecar = FakeScriptSidecar([call_frame(1, "a"), end_frame("ok")])

    async def dispatch(request):
        raise AgentAbortedError("user cancelled")

    with pytest.raises(AgentAbortedError):
        await run(runner_for(sidecar), dispatch)
    assert sidecar.socket.sent_of("cancel") == [{"type": "cancel"}]


async def test_no_cancel_after_a_normal_end():
    sidecar = FakeScriptSidecar([end_frame("ok")])
    await run(runner_for(sidecar))
    assert sidecar.socket.sent_of("cancel") == []


async def test_refused_names_stay_out_of_the_learned_tools():
    sidecar = FakeScriptSidecar(
        [
            call_frame(1, "get_a"),
            call_frame(2, "forged"),
            call_frame(3, "write_x"),
            call_frame(4, "get_b"),
            end_frame("ok"),
        ]
    )

    async def dispatch(request):
        errors = {"forged": "tool_not_available", "write_x": "writes_must_be_proposed"}
        if request.tool in errors:
            return DispatchReply(ok=False, error=errors[request.tool])
        if request.tool == "get_b":
            return DispatchReply(ok=False, error="upstream 500")
        return DispatchReply(ok=True, value=1)

    learning = AsyncMock()
    await run(runner_for(sidecar, learning=learning), dispatch)
    await _drain()
    assert learning.record.await_args.kwargs["tools"] == ["get_a", "get_b"]


async def test_three_runs_through_the_runner_yield_one_candidate_with_the_user_turn():
    ledger = FakeLedger()
    admission = AsyncMock()
    admission.candidate_exists = AsyncMock(return_value=False)
    learning = ScriptLearning(action_record_store=ledger, admission=admission)
    turn = ScriptContext(
        user_turn="what did I spend most on this month? " + "x" * 200,
        message_id=str(uuid4()),
        thread_id=str(uuid4()),
    )
    for i in range(3):
        sidecar = FakeScriptSidecar(
            [call_frame(1, "get_a"), call_frame(2, "get_b"), end_frame("ok")]
        )
        runner = runner_for(sidecar, learning=learning)
        await runner.run(
            script_id=str(uuid4()),
            agent="finance",
            source=f"z.finish({i})",
            stub="",
            limits=ScriptLimits(),
            dispatch=ok_dispatch,
            context=turn,
        )
        await _drain()
    admission.submit_procedure_candidate.assert_awaited_once()
    cand = admission.submit_procedure_candidate.await_args.args[0]
    assert cand.trigger == turn.user_turn[:120]
    assert cand.steps == ["z.finish(2)"]
    for row in ledger.rows.values():
        assert str(row.context.message_id) == turn.message_id
        assert str(row.context.thread_id) == turn.thread_id
