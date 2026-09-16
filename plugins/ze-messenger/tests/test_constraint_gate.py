from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from ze_agents.base_agent import BaseAgent
from ze_agents.hooks import clear_hooks, register_hook
from ze_agents.tool import get_tool
from ze_agents.types import AgentContext, AgentResult
from ze_memory.constraint_veto import ConstraintVetoHook, ReviewedConstraint
import ze_messenger.agents.messenger.tools  # noqa: F401


def _ctx() -> AgentContext:
    return AgentContext(session_id="s1", prompt="send it", intent="create")


def _agent() -> BaseAgent:
    class _A(BaseAgent):
        name = "test"
        description = "test"
        tools = []

        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=self.name, response="ok")

    return _A()


def test_send_email_is_constraint_gated():
    assert get_tool("send_email").constraint_gate is True


def test_draft_email_is_constraint_gated():
    assert get_tool("draft_email").constraint_gate is True


def test_list_emails_is_not_constraint_gated():
    assert get_tool("list_emails").constraint_gate is False


async def test_send_email_never_contact_is_blocked():
    ran = []
    original = get_tool("send_email").func

    async def _trap(**kwargs):
        ran.append(kwargs)
        return {"id": "nope"}

    get_tool("send_email").func = _trap
    try:
        register_hook(
            ConstraintVetoHook(
                constraints=[ReviewedConstraint(id=uuid4(), value="never email Bob")],
                user_timezone="UTC",
                now=datetime(2026, 9, 16, 10, 0, tzinfo=ZoneInfo("UTC")),
            )
        )
        tc = await _agent().call_tool(
            "send_email",
            _ctx(),
            to="Bob",
            subject="hi",
            body="hello",
        )
        assert ran == []
        assert tc.result["veto"] is True
        assert tc.result["ok"] is False
    finally:
        get_tool("send_email").func = original
        clear_hooks()


async def test_draft_email_ignores_send_time_window():
    ran = []
    original = get_tool("draft_email").func

    async def _trap(**kwargs):
        ran.append(kwargs.get("to"))
        return {"id": "draft"}

    get_tool("draft_email").func = _trap
    try:
        register_hook(
            ConstraintVetoHook(
                constraints=[
                    ReviewedConstraint(id=uuid4(), value="never email after 22:00")
                ],
                user_timezone="UTC",
                now=datetime(2026, 9, 16, 23, 0, tzinfo=ZoneInfo("UTC")),
            )
        )
        tc = await _agent().call_tool(
            "draft_email",
            _ctx(),
            to="ada@example.com",
            subject="hi",
            body="hello",
        )
        assert ran == ["ada@example.com"]
        assert tc.success is True
    finally:
        get_tool("draft_email").func = original
        clear_hooks()


async def test_draft_email_person_level_confirms_never_contact():
    ran = []
    original = get_tool("draft_email").func

    async def _trap(**kwargs):
        ran.append(kwargs.get("to"))
        return {"id": "draft"}

    get_tool("draft_email").func = _trap
    try:
        register_hook(
            ConstraintVetoHook(
                constraints=[ReviewedConstraint(id=uuid4(), value="never email Bob")],
                user_timezone="UTC",
            )
        )
        tc = await _agent().call_tool(
            "draft_email",
            _ctx(),
            to="Bob",
            subject="hi",
            body="hello",
        )
        assert ran == []
        assert tc.result["veto"] is True
    finally:
        get_tool("draft_email").func = original
        clear_hooks()
