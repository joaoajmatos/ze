"""Retry rollback end to end with fake agents and in-memory stores (Phase 180 T029).

Real: handle_retry, the plan guard, retry_eligibility, run_rollback, BaseAgent.call_tool
and run_undo, record_trace, the confirmation resume. Fake: the model, the graph (the
regeneration calls tools directly), the message store, the interface.
"""

from __future__ import annotations

from ze_agents.types import WriteGateState
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.errors import RetryFailedError
from ze_agents.park import ApprovedCall
from ze_agents.registry import clear_registry, register_instance
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool, undo_payload
from ze_agents.types import AgentContext, AgentResult
from ze_api.api.ws import turns
from ze_api.api.ws.confirmation import handle_confirm
from ze_api.api.ws.turns import handle_retry
from ze_core.conversation.messages.types import Message
from ze_core.conversation.retry import retry_eligibility
from ze_core.orchestration.nodes.trace import record_trace

THREAD = "t1"


# ── fakes ────────────────────────────────────────────────────────────────────


class World:
    """The domain state the tools change."""

    def __init__(self) -> None:
        self.reminders: dict[str, str] = {}
        self.unreachable: set[str] = set()  # reminders whose cancel fails
        self.sent: list[str] = []


class MemStore:
    def __init__(self) -> None:
        self.msgs: dict[UUID, Message] = {}
        self.traces: dict[UUID, object] = {}
        self.order: list[UUID] = []

    async def save(self, msg: Message) -> None:
        self.msgs[msg.id] = msg
        self.order.append(msg.id)

    async def save_trace(self, mid, trace) -> None:
        self.traces[mid] = trace

    async def get_message(self, mid):
        return self.msgs.get(mid)

    async def get_trace(self, mid):
        return self.traces.get(mid)

    async def latest_assistant_id(self, thread_id):
        for mid in reversed(self.order):
            m = self.msgs[mid]
            if m.thread_id == thread_id and m.role == "assistant" and not m.replaced_by:
                return mid
        return None

    async def previous_user_message(self, mid):
        idx = self.order.index(mid)
        for other in reversed(self.order[:idx]):
            if self.msgs[other].role == "user":
                return self.msgs[other]
        return None

    async def mark_superseded(self, old, new):
        if new not in self.msgs or self.msgs[old].replaced_by:
            return False
        self.msgs[old].replaced_by = new
        return True

    async def set_rollback(self, mid, record) -> None:
        self.msgs[mid].rollback = record


def _msg(role: str, text: str, **kw) -> Message:
    return Message(
        id=kw.pop("id", uuid4()),
        role=role,  # type: ignore[arg-type]
        text=text,
        components=[],
        read=True,
        created_at=datetime.now(timezone.utc),
        thread_id=THREAD,
        **kw,
    )


class Reminders(BaseAgent):
    name = "reminders"
    description = "d"
    tools = ["set_e2e", "cancel_e2e"]

    def __init__(self, world: World, llm) -> None:
        self.world = world
        self.llm = llm

    def tool_deps(self) -> dict:
        return {"world": self.world}

    async def run(self, ctx):
        return AgentResult(agent=self.name, response="ok")


class Companion(BaseAgent):
    name = "companion"
    description = "d"
    tools = ["send_e2e"]

    def __init__(self, world: World) -> None:
        self.world = world

    def tool_deps(self) -> dict:
        return {"world": self.world}

    async def run(self, ctx):
        return AgentResult(agent=self.name, response="ok")


@pytest.fixture(autouse=True)
def tools():
    clear_registry()
    clear_tool_registry()

    @tool(
        access=ToolAccess.WRITE,
        description="set",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="cancel_e2e",
        undo_note="Does not recall a shown notification",
        effect_phrase="set a reminder",
    )
    async def set_e2e(world, label: str) -> dict:
        rid = str(uuid4())
        world.reminders[rid] = label
        return {"id": rid, "undo": undo_payload(reminder_id=rid)}

    @tool(
        access=ToolAccess.WRITE,
        description="cancel",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="cancelled a reminder",
    )
    async def cancel_e2e(world, reminder_id: str) -> dict:
        if reminder_id in world.unreachable or reminder_id not in world.reminders:
            return {"error": "reminder already fired"}
        world.reminders.pop(reminder_id)
        return {"cancelled": reminder_id}

    @tool(
        access=ToolAccess.WRITE,
        description="send",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="sent an email",
    )
    async def send_e2e(world, to: str) -> dict:
        world.sent.append(to)
        return {"sent": to}

    yield
    clear_registry()
    clear_tool_registry()


class Env:
    def __init__(self) -> None:
        self.world = World()
        self.llm = MagicMock()
        self.reminders = Reminders(self.world, self.llm)
        self.companion = Companion(self.world)
        register_instance("reminders", self.reminders)
        register_instance("companion", self.companion)
        self.store = MemStore()
        self.frames: list[dict] = []
        self.conn = MagicMock()
        self.conn.send_frame = AsyncMock(
            side_effect=lambda frame, thread_id=None: self.frames.append(frame)
        )
        self.conn.is_busy = MagicMock(return_value=True)
        self.conn.try_set_busy = MagicMock(return_value=True)
        self.conn.clear_busy = MagicMock()
        self.feedback = AsyncMock()
        self.conf = AsyncMock()
        self.conf.get_pending_for_thread = AsyncMock(return_value=[])
        self.container = MagicMock()
        self.container.held_write_store = None
        self.container.is_thread_locked = MagicMock(return_value=False)
        self.container.translations = None
        self.container.retry_rewindable = AsyncMock(return_value=True)
        self.container.message_store = self.store

        @asynccontextmanager
        async def _hold(thread_id):
            yield

        self.container.hold_thread = _hold

        async def _send(
            text,
            thread_id=None,
            components=None,
            trace=None,
            message_id=None,
            replaces=None,
            after_save=None,
        ):
            msg = _msg(
                "assistant",
                text,
                id=UUID(message_id) if message_id else uuid4(),
                replaces=replaces,
            )
            await self.store.save(msg)
            if trace is not None:
                await self.store.save_trace(msg.id, trace)
            if after_save is not None and not await after_save():
                return False
            return True

        self.container.interface.send_with_thread = AsyncMock(side_effect=_send)
        self.regen = AsyncMock(side_effect=RetryFailedError("no regen configured"))
        self.container.invoke_retry_turn = self.regen

    # ── turns ────────────────────────────────────────────────────────────────

    async def _trace_for(self, calls: list):
        result = AgentResult(agent="companion", response="done", tool_calls=calls)
        state = {
            "envelope": SimpleNamespace(
                primary_agent="companion",
                routing_method="embedding",
                confidence=0.9,
                score_gap=0.1,
                is_compound=False,
                subtasks=[],
            ),
            "agent_result": result,
            "agent_context": AgentContext(session_id=THREAD, prompt="x"),
        }
        return (await record_trace(state, {"configurable": {}}))["message_trace"]

    async def _run_tools(self, steps, *, retry: bool):
        ctx = AgentContext(session_id=THREAD, prompt="x", write_gate=WriteGateState(retry_mode=retry))
        calls = []
        for agent, name, args in steps:
            # The original turn ran its calls with the user's approval; a retry
            # runs unapproved, so it refuses irreversible writes (Phase 181).
            approval = None if retry else ApprovedCall("e2e")
            calls.append(
                await agent.call_tool(
                    name,
                    ctx,
                    _lm_args=args,
                    _approval=approval,
                    world=self.world,
                    **args,
                )
            )
        return calls

    async def original_turn(self, *steps) -> Message:
        """steps: (agent, tool, args). Stores the user message and the traced reply."""
        await self.store.save(_msg("user", "remind me to call Ana"))
        calls = await self._run_tools(steps, retry=False)
        reply = _msg("assistant", "Done.")
        await self.store.save(reply)
        await self.store.save_trace(reply.id, await self._trace_for(calls))
        return reply

    def regenerates(self, *steps) -> None:
        async def _regen(thread_id, text, *, replaces, config_extra=None):
            calls = await self._run_tools(steps, retry=True)
            return SimpleNamespace(
                response="Fresh reply.",
                interrupted=False,
                message_id=str(uuid4()),
                config={"configurable": {"thread_id": thread_id}},
                final_state={
                    "components": [],
                    "message_trace": await self._trace_for(calls),
                },
            )

        self.regen = AsyncMock(side_effect=_regen)
        self.container.invoke_retry_turn = self.regen

    # ── helpers ──────────────────────────────────────────────────────────────

    async def plan_ids(self, reply: Message) -> list[str]:
        return [e.entry_id for e in (await self.eligibility(reply)).plan]

    async def eligibility(self, reply: Message):
        return retry_eligibility(
            await self.store.get_message(reply.id),
            await self.store.get_trace(reply.id),
            latest_assistant_id=await self.store.latest_assistant_id(THREAD),
            rollback=(await self.store.get_message(reply.id)).rollback,
        )

    async def retry(self, reply: Message, confirmed=None):
        frame = {"type": "retry", "message_id": str(reply.id), "thread_id": THREAD}
        if confirmed is not None:
            frame["confirmed_plan"] = confirmed
        return await handle_retry(
            frame,
            self.container,
            self.store,
            self.conn,
            feedback_store=self.feedback,
            confirmation_store=self.conf,
        )

    def errors(self) -> list[dict]:
        return [f for f in self.frames if f["type"] == "error"]

    def of(self, kind: str) -> list[dict]:
        return [f for f in self.frames if f["type"] == kind]

    def tools_of(self, agent, name, args):
        return (agent, name, args)

    def set_reminder(self, label="call Ana"):
        return (self.reminders, "set_e2e", {"label": label})

    def send_email(self):
        return (self.companion, "send_e2e", {"to": "ana@example.com"})


@pytest.fixture
def env():
    return Env()


# ── scenarios ────────────────────────────────────────────────────────────────


async def test_us1_rollback_then_regeneration_sets_a_new_reminder(env):
    reply = await env.original_turn(env.set_reminder("call Ana at 4"))
    [old_id] = list(env.world.reminders)
    ids = await env.plan_ids(reply)
    assert len(ids) == 1
    seen_at_regen = {}

    async def _regen(thread_id, text, *, replaces, config_extra=None):
        # the undo must already have happened when the regeneration starts
        seen_at_regen["old_still_there"] = old_id in env.world.reminders
        return await inner(
            thread_id, text, replaces=replaces, config_extra=config_extra
        )

    env.regenerates(env.set_reminder("call Ana at 5"))
    inner = env.regen.side_effect
    env.regen = AsyncMock(side_effect=_regen)
    env.container.invoke_retry_turn = env.regen

    # the rollback executor never runs a model loop (SC-007)
    with (
        patch.object(BaseAgent, "run", side_effect=AssertionError("model run")),
        patch.object(BaseAgent, "agentic_loop", side_effect=AssertionError("loop")),
    ):
        await env.retry(reply, ids)

    assert seen_at_regen == {"old_still_there": False}
    assert env.errors() == []
    assert old_id not in env.world.reminders
    assert list(env.world.reminders.values()) == ["call Ana at 5"]
    env.feedback.append.assert_awaited_once()  # retry_requested recorded (FR-025)
    old = await env.store.get_message(reply.id)
    assert old.replaced_by is not None
    assert old.rollback.state == "superseded"
    assert [e.outcome for e in old.rollback.entries] == ["undone"]
    # the new reply is itself retryable with a one-entry plan (FR-021)
    new_id = old.replaced_by
    new_trace = await env.store.get_trace(new_id)
    assert new_trace.rollback.replaces == str(reply.id)
    elig = await env.eligibility(await env.store.get_message(new_id))
    assert elig.available is True
    assert len(elig.plan) == 1
    assert elig.plan[0].undo_args["reminder_id"] in env.world.reminders


async def test_us4_mid_plan_failure_keeps_the_original_and_stops(env):
    reply = await env.original_turn(
        env.set_reminder("first"), env.set_reminder("second")
    )
    first, second = list(env.world.reminders)
    ids = await env.plan_ids(reply)
    assert len(ids) == 2
    env.world.unreachable.add(first)  # undone second (reverse order), first fails
    env.regenerates(env.set_reminder("never"))

    await env.retry(reply, ids)

    [err] = env.errors()
    assert err["code"] == "retry_partial"
    assert err["rolled_back"] is True
    env.regen.assert_not_awaited()
    assert second not in env.world.reminders
    assert first in env.world.reminders
    old = await env.store.get_message(reply.id)
    assert old.replaced_by is None
    assert [e.outcome for e in old.rollback.entries] == ["undone", "failed"]
    assert old.rollback.state == "partial"
    elig = await env.eligibility(reply)
    assert elig.available is False
    assert elig.reason_code.value == "undo_failed"


async def test_regeneration_failure_after_full_undo_then_a_text_only_retry(env):
    reply = await env.original_turn(env.set_reminder())
    ids = await env.plan_ids(reply)
    env.regen = AsyncMock(side_effect=RetryFailedError("boom"))
    env.container.invoke_retry_turn = env.regen

    await env.retry(reply, ids)

    [err] = env.errors()
    assert err["code"] == "retry_failed"
    assert err["rolled_back"] is True
    assert "unchanged" not in err["detail"]
    assert env.world.reminders == {}
    old = await env.store.get_message(reply.id)
    assert old.rollback.state == "rolled_back_retry_failed"
    assert old.replaced_by is None

    # Retry stays available, text-only: nothing left to undo, one press
    elig = await env.eligibility(reply)
    assert elig.available is True and elig.plan == []
    env.frames.clear()
    env.regenerates()
    await env.retry(reply)
    assert env.errors() == []
    old = await env.store.get_message(reply.id)
    assert old.replaced_by is not None
    assert old.rollback.state == "superseded"


async def test_plan_changed_changes_nothing(env):
    reply = await env.original_turn(env.set_reminder())
    env.regenerates()

    await env.retry(reply, ["not-the-current-entry"])

    [err] = env.errors()
    assert err["reason_code"] == "plan_changed"
    assert [e["tool"] for e in err["plan"]] == ["set_e2e"]
    assert len(env.world.reminders) == 1
    env.regen.assert_not_awaited()
    assert (await env.store.get_message(reply.id)).rollback is None
    env.feedback.append.assert_not_awaited()


async def test_missing_confirmation_changes_nothing(env):
    reply = await env.original_turn(env.set_reminder())
    await env.retry(reply, None)
    assert env.errors()[0]["reason_code"] == "undo_not_confirmed"
    assert len(env.world.reminders) == 1


async def test_regenerated_turn_cannot_start_an_irreversible_action(env):
    reply = await env.original_turn(env.set_reminder())
    ids = await env.plan_ids(reply)
    env.regenerates(env.set_reminder("call Ana at 5"), env.send_email())

    await env.retry(reply, ids)

    assert env.world.sent == []  # refused at dispatch (FR-019)
    assert list(env.world.reminders.values()) == ["call Ana at 5"]
    old = await env.store.get_message(reply.id)
    new_trace = await env.store.get_trace(old.replaced_by)
    email = next(c for c in new_trace.tool_calls if c.name == "send_e2e")
    assert email.gate == "refused" and email.success is False


async def test_reminder_with_an_email_is_not_retryable(env):
    reply = await env.original_turn(env.set_reminder(), env.send_email())
    elig = await env.eligibility(reply)
    assert elig.available is False
    # Under Phase 181 the irreversible send ran only because the user approved it.
    assert elig.reason_code.value == "confirmed_action"
    await env.retry(reply, [])
    assert env.errors()[0]["reason_code"] == "confirmed_action"
    assert len(env.world.reminders) == 1


def _pending_row_store() -> AsyncMock:
    store = AsyncMock()
    store.get_pending = AsyncMock(
        return_value={"thread_id": THREAD, "request_id": "req-1", "actions": {}}
    )
    store.clear = AsyncMock(return_value=True)
    return store


async def test_pause_at_confirmation_then_deny_still_supersedes(env):
    reply = await env.original_turn(env.set_reminder())
    ids = await env.plan_ids(reply)
    retry_config = {
        "configurable": {
            "thread_id": THREAD,
            "retry_mode": True,
            "retry_replaces": str(reply.id),
        }
    }
    paused = SimpleNamespace(
        interrupted=True,
        response=None,
        message_id="",
        config=retry_config,
        final_state={},
    )
    env.regen = AsyncMock(return_value=paused)
    env.container.invoke_retry_turn = env.regen
    gate = ("req-1", retry_config)
    with patch.object(turns, "send_confirmation_request", AsyncMock(return_value=gate)):
        result = await env.retry(reply, ids)
    assert result == gate
    old = await env.store.get_message(reply.id)
    assert old.rollback.state == "rolled_back_awaiting_confirmation"
    assert old.replaced_by is None
    assert env.world.reminders == {}

    # the person denies; the graph answers without the gated action
    new_id = uuid4()
    env.container.graph.aget_state = AsyncMock(
        return_value=SimpleNamespace(interrupts=[()])
    )
    env.container.resume_turn = AsyncMock(
        return_value=SimpleNamespace(
            response="Okay, I left it.",
            interrupted=False,
            error=None,
            message_id=str(new_id),
            config=retry_config,
            final_state={"components": [], "message_trace": await env._trace_for([])},
        )
    )
    await handle_confirm(
        MagicMock(),
        {"type": "confirm", "id": "req-1", "choice": "deny"},
        env.container,
        env.conn,
        retry_config,
        thread_id=THREAD,
        confirmation_store=_pending_row_store(),
        msg_store=env.store,
    )
    old = await env.store.get_message(reply.id)
    assert old.replaced_by == new_id
    assert old.rollback.state == "superseded"
    assert env.of("message_superseded")[-1]["replaced_by"] == str(new_id)
    assert (await env.store.get_message(new_id)).replaces == reply.id


async def test_the_thread_lock_is_held_through_regeneration_and_not_reentered(env):
    import asyncio

    from ze_workspace.turn_lock import ThreadTurnLock

    lock = ThreadTurnLock()

    @asynccontextmanager
    async def _hold(thread_id):
        async with lock.acquire(thread_id):
            yield

    env.container.hold_thread = _hold
    env.container.is_thread_locked = lock.is_locked
    reply = await env.original_turn(env.set_reminder())
    ids = await env.plan_ids(reply)
    held_during_regen = []
    follow_up_ran_after = []
    release = asyncio.Event()

    async def _regen(thread_id, text, *, replaces, config_extra=None):
        held_during_regen.append(lock.is_locked(THREAD))

        async def _follow_up():
            async with lock.acquire(THREAD):
                follow_up_ran_after.append(release.is_set())

        task = asyncio.create_task(_follow_up())
        await asyncio.sleep(0)
        assert follow_up_ran_after == []  # blocked while the retry holds the thread
        release.set()
        env.follow_up = task
        return await inner(
            thread_id, text, replaces=replaces, config_extra=config_extra
        )

    env.regenerates(env.set_reminder("again"))
    inner = env.regen.side_effect
    env.container.invoke_retry_turn = AsyncMock(side_effect=_regen)

    await asyncio.wait_for(env.retry(reply, ids), timeout=5)
    await asyncio.wait_for(env.follow_up, timeout=5)

    assert held_during_regen == [True]
    assert follow_up_ran_after == [True]
    assert not lock.is_locked(THREAD)
    assert env.errors() == []
