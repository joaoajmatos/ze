from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from ze_agents.types import AgentContext
from ze_core.orchestration.nodes.skills import match_skills


@dataclass
class _FakeSkill:
    name: str
    description: str = "does a thing"
    allowed_tools: list[str] | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class _FakeMatch:
    skill: _FakeSkill
    trigger: str = "automatic"
    similarity: float | None = 0.8


def _matcher(matches: list[_FakeMatch] | None = None, error: bool = False) -> Any:
    m = AsyncMock()
    if error:
        m.match = AsyncMock(side_effect=RuntimeError("boom"))
    else:
        m.match = AsyncMock(return_value=matches or [])
    return m


def _config(matcher: Any = None) -> dict:
    return {"configurable": {"skill_matcher": matcher}}


_MISSING = object()


def _state(prompt: str = "hi", agent_context: Any = _MISSING) -> dict:
    if agent_context is _MISSING:
        agent_context = AgentContext(session_id="s1", prompt=prompt, intent="read")
    return {
        "prompt": prompt,
        "image_caption": None,
        "agent_context": agent_context,
    }


@pytest.mark.asyncio
async def test_no_op_when_no_matcher_injected():
    result = await match_skills(_state(), _config(matcher=None))
    assert result == {}


@pytest.mark.asyncio
async def test_no_op_when_no_agent_context_yet():
    result = await match_skills(
        _state(agent_context=None),
        _config(matcher=_matcher([_FakeMatch(_FakeSkill("Pirate Speak"))])),
    )
    assert result == {}


@pytest.mark.asyncio
async def test_no_op_when_no_skills_matched():
    result = await match_skills(_state(), _config(matcher=_matcher([])))
    assert result == {}


@pytest.mark.asyncio
async def test_populates_agent_context_active_skills_and_skill_tool_names():
    skill = _FakeSkill("Pirate Speak", allowed_tools=["search"])
    match = _FakeMatch(skill)
    ctx = AgentContext(session_id="s1", prompt="hi", intent="read")
    state = _state(agent_context=ctx)

    result = await match_skills(state, _config(matcher=_matcher([match])))

    assert result["agent_context"] is ctx
    assert ctx.active_skills == [skill]
    assert ctx.skill_tool_names == ["search"]
    assert result["skill_matches"] == [match]


@pytest.mark.asyncio
async def test_skill_tool_names_none_when_no_skill_restricts_tools():
    skill = _FakeSkill("Pirate Speak", allowed_tools=None)
    match = _FakeMatch(skill)
    ctx = AgentContext(session_id="s1", prompt="hi", intent="read")

    await match_skills(_state(agent_context=ctx), _config(matcher=_matcher([match])))

    assert ctx.skill_tool_names is None


@pytest.mark.asyncio
async def test_multiple_matched_skills_tool_names_intersected():
    skill_a = _FakeSkill("A", allowed_tools=["tool_a", "tool_b"])
    skill_b = _FakeSkill("B", allowed_tools=["tool_b", "tool_c"])
    ctx = AgentContext(session_id="s1", prompt="hi", intent="read")

    await match_skills(
        _state(agent_context=ctx),
        _config(matcher=_matcher([_FakeMatch(skill_a), _FakeMatch(skill_b)])),
    )

    assert ctx.skill_tool_names == ["tool_b"]


@pytest.mark.asyncio
async def test_matcher_error_is_swallowed():
    ctx = AgentContext(session_id="s1", prompt="hi", intent="read")
    result = await match_skills(
        _state(agent_context=ctx), _config(matcher=_matcher(error=True))
    )
    assert result == {}
