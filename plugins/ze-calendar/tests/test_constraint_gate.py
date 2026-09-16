from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from ze_agents.base_agent import BaseAgent
from ze_agents.hooks import clear_hooks, register_hook
from ze_agents.tool import get_tool
from ze_agents.types import AgentContext, AgentResult
from ze_memory.constraint_veto import ConstraintVetoHook, ReviewedConstraint
import ze_calendar.agents.calendar.tools  # noqa: F401
import ze_calendar.agents.reminders.tools  # noqa: F401


def _ctx() -> AgentContext:
    return AgentContext(session_id="s1", prompt="schedule it", intent="create")


def _agent() -> BaseAgent:
    class _A(BaseAgent):
        name = "test"
        description = "test"
        tools = []

        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=self.name, response="ok")

    return _A()


def test_calendar_mutations_are_constraint_gated():
    assert get_tool("create_event").constraint_gate is True
    assert get_tool("update_event").constraint_gate is True
    assert get_tool("delete_event").constraint_gate is True
    assert get_tool("list_events").constraint_gate is False


def test_reminder_writes_are_constraint_gated():
    assert get_tool("set_reminder").constraint_gate is True
    assert get_tool("cancel_reminder").constraint_gate is True
    assert get_tool("list_reminders").constraint_gate is False


async def _assert_blocked(name: str, **kwargs):
    ran = []
    original = get_tool(name).func

    async def _trap(**_kwargs):
        ran.append(True)
        return {"id": "nope"}

    get_tool(name).func = _trap
    try:
        register_hook(
            ConstraintVetoHook(
                constraints=[
                    ReviewedConstraint(id=uuid4(), value="never schedule after 22:00")
                ],
                user_timezone="UTC",
                now=datetime(2026, 9, 16, 23, 0, tzinfo=ZoneInfo("UTC")),
            )
        )
        tc = await _agent().call_tool(name, _ctx(), **kwargs)
        assert ran == []
        assert tc.result["veto"] is True
        assert tc.result["ok"] is False
    finally:
        get_tool(name).func = original
        clear_hooks()


async def test_create_event_in_forbidden_window_is_blocked():
    await _assert_blocked(
        "create_event",
        summary="dentist",
        start="2026-09-16T23:00:00+00:00",
        end="2026-09-16T23:30:00+00:00",
    )


async def test_update_event_in_forbidden_window_is_blocked():
    await _assert_blocked(
        "update_event",
        event_id="evt-1",
        start="2026-09-16T23:00:00+00:00",
    )


async def test_delete_event_with_calendar_constraint_confirms_or_blocks():
    ran = []
    original = get_tool("delete_event").func

    async def _trap(**_kwargs):
        ran.append(True)

    get_tool("delete_event").func = _trap
    try:
        register_hook(
            ConstraintVetoHook(
                constraints=[
                    ReviewedConstraint(
                        id=uuid4(), value="do not change calendar events"
                    )
                ],
                user_timezone="UTC",
            )
        )
        tc = await _agent().call_tool("delete_event", _ctx(), event_id="evt-1")
        assert ran == []
        assert tc.result["veto"] is True
    finally:
        get_tool("delete_event").func = original
        clear_hooks()


async def test_set_reminder_in_forbidden_window_is_blocked():
    ran = []
    original = get_tool("set_reminder").func

    async def _trap(**_kwargs):
        ran.append(True)
        return {"id": "r"}

    get_tool("set_reminder").func = _trap
    try:
        register_hook(
            ConstraintVetoHook(
                constraints=[
                    ReviewedConstraint(
                        id=uuid4(), value="never set a reminder after 22:00"
                    )
                ],
                user_timezone="UTC",
                now=datetime(2026, 9, 16, 23, 0, tzinfo=ZoneInfo("UTC")),
            )
        )
        tc = await _agent().call_tool(
            "set_reminder",
            _ctx(),
            label="pills",
            fire_at="2026-09-16T23:30:00+00:00",
        )
        assert ran == []
        assert tc.result["veto"] is True
    finally:
        get_tool("set_reminder").func = original
        clear_hooks()


async def test_cancel_reminder_with_reminder_constraint_does_not_complete_silently():
    ran = []
    original = get_tool("cancel_reminder").func

    async def _trap(**_kwargs):
        ran.append(True)
        return {"cancelled": "pills"}

    get_tool("cancel_reminder").func = _trap
    try:
        register_hook(
            ConstraintVetoHook(
                constraints=[
                    ReviewedConstraint(id=uuid4(), value="do not cancel reminders")
                ],
                user_timezone="UTC",
            )
        )
        tc = await _agent().call_tool(
            "cancel_reminder",
            _ctx(),
            reminder_id="11111111-1111-1111-1111-111111111111",
        )
        assert ran == []
        assert tc.result["veto"] is True
    finally:
        get_tool("cancel_reminder").func = original
        clear_hooks()
