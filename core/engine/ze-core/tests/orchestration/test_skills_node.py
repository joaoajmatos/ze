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


@dataclass
class _Outcome:
    matches: list
    judgment: Any = None


def _matcher(
    matches: list[_FakeMatch] | None = None, error: bool = False, judgment: Any = None
) -> Any:
    m = AsyncMock()
    if error:
        m.match = AsyncMock(side_effect=RuntimeError("boom"))
    else:
        m.match = AsyncMock(
            return_value=_Outcome(matches=matches or [], judgment=judgment)
        )
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


# ── Phase 166: judgments ────────────────────────────────────────────────

from ze_agents.system_one import SystemOneAnswer, SystemOneResult  # noqa: E402

from ze_core.conversation.messages.types import JudgmentTrace  # noqa: E402


@dataclass
class _Judgment:
    result: Any
    question_kinds: dict
    consumed: frozenset = frozenset()
    skip_reason: str | None = None


def _ok_judgment(consumed=frozenset({"skill", "needs_skill"})) -> _Judgment:
    return _Judgment(
        result=SystemOneResult(
            outcome="ok",
            latency_ms=12,
            answers={
                "skill": SystemOneAnswer(type="choice", choice="a", confidence=0.9),
                "needs_skill": SystemOneAnswer(type="noul", noul=0.8),
            },
        ),
        question_kinds={"skill": "choice", "needs_skill": "noul"},
        consumed=consumed,
    )


@pytest.mark.asyncio
async def test_judgment_rows_appended_after_embed_route_rows():
    prior = JudgmentTrace(question_id="agent", kind="choice", latency_ms=1)
    skill = _FakeSkill("A")
    state = {**_state(), "judgments": [prior]}

    result = await match_skills(
        state,
        _config(matcher=_matcher([_FakeMatch(skill)], judgment=_ok_judgment())),
    )

    rows = result["judgments"]
    assert rows[0] is prior
    assert [r.question_id for r in rows[1:]] == ["skill", "needs_skill"]
    assert all(r.consumed for r in rows[1:])


@pytest.mark.asyncio
async def test_consumed_follows_outcome():
    result = await match_skills(
        _state(),
        _config(matcher=_matcher([], judgment=_ok_judgment(frozenset({"skill"})))),
    )
    consumed = {r.question_id: r.consumed for r in result["judgments"]}
    assert consumed == {"skill": True, "needs_skill": False}


@pytest.mark.asyncio
async def test_judgments_returned_even_when_no_skill_applies():
    result = await match_skills(
        _state(), _config(matcher=_matcher([], judgment=_ok_judgment()))
    )
    assert "judgments" in result
    assert "skill_matches" not in result and "agent_context" not in result


@pytest.mark.asyncio
async def test_skip_judgment_rows_carry_reason_and_abstain_keeps_matches():
    skip = _Judgment(
        result=SystemOneResult(outcome="skip", skip_reason="timeout"),
        question_kinds={"skill": "choice", "needs_skill": "noul"},
    )
    a = _FakeMatch(_FakeSkill("A", allowed_tools=["x"]))
    b = _FakeMatch(_FakeSkill("B", allowed_tools=["x", "y"]))
    ctx = AgentContext(session_id="s1", prompt="hi", intent="read")

    result = await match_skills(
        _state(agent_context=ctx), _config(matcher=_matcher([a, b], judgment=skip))
    )

    assert [r.skip_reason for r in result["judgments"]] == ["timeout", "timeout"]
    assert result["skill_matches"] == [a, b]
    assert ctx.skill_tool_names == ["x"]


@pytest.mark.asyncio
async def test_dropped_skill_imposes_no_restriction():
    ctx = AgentContext(session_id="s1", prompt="hi", intent="read")
    chosen = _FakeMatch(_FakeSkill("A", allowed_tools=None))

    await match_skills(
        _state(agent_context=ctx),
        _config(matcher=_matcher([chosen], judgment=_ok_judgment())),
    )

    assert ctx.skill_tool_names is None


@pytest.mark.asyncio
async def test_matcher_receives_bounded_judgment_state():
    matcher = _matcher([])
    state = {**_state(prompt="write an email"), "routing_hints": "ctx"}

    await match_skills(state, _config(matcher=matcher))

    kwargs = matcher.match.call_args.kwargs
    assert kwargs["judgment_state"] == {"user": "write an email", "context": "ctx"}
