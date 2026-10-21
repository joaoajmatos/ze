"""Trace judgment rows carry the surface and the bar in force (187b)."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_agents.types import AgentContext, AgentResult
from ze_core.conversation.messages.types import JudgmentBar, MessageTrace
from ze_core.orchestration.nodes.memory import write_memory
from ze_core.orchestration.nodes.routing import embed_route
from ze_core.orchestration.nodes.skills import match_skills
from ze_core.orchestration.nodes.tier import choose_tier
from ze_core.routing.tier import Q_DEEP, ComplexitySurfaceConfig, TierJudge
from ze_core.routing.types import RoutingEnvelope, RoutingJudgment, SubTask
from ze_memory.types import Fact, FactAdmission, MemoryContext

from tests.support.routing import FakeSystemOneClient, register_agent

OK = dict(outcome="ok", model="jev", input_tokens=10, latency_ms=5)


def _choice(name: str) -> SystemOneAnswer:
    return SystemOneAnswer(
        type="choice", choice=name, confidence=0.9, probabilities={name: 0.9}
    )


def _noul(value: float = 0.5) -> SystemOneAnswer:
    return SystemOneAnswer(type="noul", noul=value)


def _by_id(rows) -> dict:
    return {r.question_id: r for r in rows}


def _bar(name: str, value: float) -> JudgmentBar:
    return JudgmentBar(name=name, value=value)


# ── routing ──────────────────────────────────────────────────────────────────


def _routing_router(surface) -> Any:
    envelope = RoutingEnvelope(
        primary_agent="alpha",
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=False,
        subtasks=[SubTask(agent="alpha", prompt="hi")],
        requires_synthesis=False,
        judgment=RoutingJudgment(
            result=SystemOneResult(
                answers={"agent": _choice("alpha"), "multi_specialist": _noul()}, **OK
            ),
            question_kinds={"agent": "choice", "multi_specialist": "noul"},
            consumed=frozenset({"agent"}),
        ),
    )
    router = MagicMock()
    router.route = AsyncMock(return_value=envelope)
    router.screen_hint = False
    router.surface = surface
    return router


async def test_routing_rows_carry_surface_and_bars():
    router = _routing_router(
        SimpleNamespace(choice_trust=0.5, multi_specialist_hold=0.4)
    )
    out = await embed_route(
        {"session_id": "s1", "prompt": "hi"}, {"configurable": {"router": router}}
    )
    rows = _by_id(out["judgments"])
    assert {r.surface for r in rows.values()} == {"routing"}
    assert rows["agent"].bar == _bar("choice_trust", 0.5)
    assert rows["multi_specialist"].bar == _bar("multi_specialist_hold", 0.4)


async def test_routing_uncalibrated_rows_have_surface_and_null_bar():
    router = _routing_router(
        SimpleNamespace(choice_trust=None, multi_specialist_hold=None)
    )
    out = await embed_route(
        {"session_id": "s1", "prompt": "hi"}, {"configurable": {"router": router}}
    )
    rows = out["judgments"]
    assert {r.surface for r in rows} == {"routing"}
    assert all(r.bar is None for r in rows)


async def test_routing_reads_the_surface_in_force_each_turn():
    router = _routing_router(
        SimpleNamespace(choice_trust=0.5, multi_specialist_hold=0.4)
    )
    config = {"configurable": {"router": router}}
    state = {"session_id": "s1", "prompt": "hi"}
    first = _by_id((await embed_route(state, config))["judgments"])
    router.surface = SimpleNamespace(choice_trust=0.8, multi_specialist_hold=0.4)
    second = _by_id((await embed_route(state, config))["judgments"])
    assert first["agent"].bar.value == 0.5
    assert second["agent"].bar.value == 0.8


# ── skills ───────────────────────────────────────────────────────────────────


@dataclass
class _Outcome:
    matches: list
    judgment: Any = None


def _skills_matcher(surface) -> Any:
    judgment = RoutingJudgment(
        result=SystemOneResult(
            answers={"skill": _choice("a"), "needs_skill": _noul()}, **OK
        ),
        question_kinds={"skill": "choice", "needs_skill": "noul"},
        consumed=frozenset({"skill"}),
    )
    matcher = AsyncMock()
    matcher.match = AsyncMock(return_value=_Outcome(matches=[], judgment=judgment))
    matcher.surface = surface
    return matcher


async def test_skills_rows_carry_surface_and_bars():
    matcher = _skills_matcher(SimpleNamespace(choice_trust=0.75, needs_skill_hold=0.6))
    state = {
        "prompt": "hi",
        "image_caption": None,
        "agent_context": AgentContext(session_id="s1", prompt="hi"),
    }
    out = await match_skills(state, {"configurable": {"skill_matcher": matcher}})
    rows = _by_id(out["judgments"])
    assert {r.surface for r in rows.values()} == {"skills"}
    assert rows["skill"].bar == _bar("choice_trust", 0.75)
    assert rows["needs_skill"].bar == _bar("needs_skill_hold", 0.6)


async def test_skills_uncalibrated_rows_have_null_bar():
    matcher = _skills_matcher(SimpleNamespace(choice_trust=0.75, needs_skill_hold=None))
    state = {
        "prompt": "hi",
        "image_caption": None,
        "agent_context": AgentContext(session_id="s1", prompt="hi"),
    }
    out = await match_skills(state, {"configurable": {"skill_matcher": matcher}})
    rows = _by_id(out["judgments"])
    assert rows["skill"].bar == _bar("choice_trust", 0.75)
    assert rows["needs_skill"].surface == "skills"
    assert rows["needs_skill"].bar is None


# ── complexity ───────────────────────────────────────────────────────────────


async def test_tier_row_carries_simple_max():
    register_agent("t187", model="full-m", model_simple="light-m")
    envelope = RoutingEnvelope(
        primary_agent="t187",
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=False,
        subtasks=[SubTask(agent="t187", prompt="thanks", model="full-m")],
        requires_synthesis=False,
    )
    client = FakeSystemOneClient(SystemOneResult(answers={Q_DEEP: _noul(0.9)}, **OK))
    judge = TierJudge(client, ComplexitySurfaceConfig(enabled=True, simple_max=0.2), {})
    state = {
        "session_id": "s1",
        "prompt": "thanks",
        "image_caption": None,
        "agent_context": AgentContext(
            session_id="s1",
            prompt="thanks",
            messages=[{"role": "user", "content": "thanks"}],
        ),
        "memory_context": None,
        "routing_hints": None,
        "envelope": envelope,
        "judgments": [],
    }
    out = await choose_tier(state, {"configurable": {"tier_judge": judge}})
    [row] = out["judgments"]
    assert row.surface == "complexity"
    assert row.bar == _bar("simple_max", 0.2)


# ── commitment intake and fact fallback ──────────────────────────────────────

_INTAKE_BARS = {
    "choice_hold": 0.7,
    "family_hold": 0.71,
    "biography_hold": 0.55,
    "loop_hold": 0.6,
    "explicit_hold": 0.95,
    "resolves_hold": 0.8,
}
_INTAKE_IDS = {
    "commitment": "choice_hold",
    "family": "family_hold",
    "biography": "biography_hold",
    "is_open_concern": "loop_hold",
    "explicit_declaration": "explicit_hold",
    "resolves_existing": "resolves_hold",
}


def _intake() -> Any:
    answers = {
        "commitment": _choice("fact"),
        "family": _choice("preference"),
        "biography": _noul(0.9),
        "is_open_concern": _noul(0.1),
        "explicit_declaration": _noul(0.1),
        "resolves_existing": _noul(0.1),
    }
    return SimpleNamespace(
        outcome=SimpleNamespace(kind="persist_fact", reason="family", link_kind=None),
        fact=FactAdmission(
            facts=[Fact(predicate="preference", value="aisle seats")], path="system_one"
        ),
        loop=None,
        links=(),
        judgment=SystemOneResult(answers=answers, **OK),
        question_kinds={qid: a.type for qid, a in answers.items()},
        consumed=frozenset({"commitment", "family", "biography"}),
        skip_reason=None,
    )


def _trace() -> MessageTrace:
    return MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.3,
        is_compound=False,
        subtasks=[],
    )


def _memory_config(*, intake=None, extractor=None, settings=None) -> dict:
    store = AsyncMock()
    store.write_episode = AsyncMock()
    embedder = MagicMock()
    embedder.encode_passage = embedder.encode_query = MagicMock(return_value=[0.1])
    configurable: dict = {
        "memory_store": store,
        "embedder": embedder,
        "thread_id": "s1",
        "settings": settings,
    }
    if intake is not None:

        async def _call(_cfg, **_kw):
            return intake

        configurable["commitment_intake"] = _call
    if extractor is not None:
        configurable["fact_extractor"] = extractor
    return {"configurable": configurable}


def _memory_state() -> dict:
    return {
        "session_id": "s1",
        "agent_context": AgentContext(
            session_id="s1", prompt="I prefer aisle seats", memory=MemoryContext()
        ),
        "agent_result": AgentResult(agent="companion", response="Noted."),
        "subtask_results": [],
        "messages": [],
        "input_modality": "text",
        "message_trace": _trace(),
    }


def _settings(**bars) -> dict:
    return {
        "system_one": {"surfaces": {"commitment_intake": {"enabled": True, **bars}}}
    }


async def _write(config: dict) -> list:
    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ):
        out = await write_memory(_memory_state(), config)
    return out["message_trace"].judgments


async def test_commitment_intake_rows_carry_the_six_holds():
    rows = _by_id(
        await _write(
            _memory_config(intake=_intake(), settings=_settings(**_INTAKE_BARS))
        )
    )
    for qid, bar_name in _INTAKE_IDS.items():
        assert rows[qid].surface == "commitment_intake"
        assert rows[qid].bar == _bar(bar_name, _INTAKE_BARS[bar_name]), qid


async def test_commitment_intake_outcome_row_has_surface_and_no_bar():
    rows = _by_id(
        await _write(
            _memory_config(intake=_intake(), settings=_settings(**_INTAKE_BARS))
        )
    )
    assert rows["intake_outcome"].surface == "commitment_intake"
    assert rows["intake_outcome"].bar is None


async def test_commitment_intake_uncalibrated_bars_are_null():
    partial = {k: v for k, v in _INTAKE_BARS.items() if k != "loop_hold"}
    rows = _by_id(
        await _write(_memory_config(intake=_intake(), settings=_settings(**partial)))
    )
    assert rows["is_open_concern"].surface == "commitment_intake"
    assert rows["is_open_concern"].bar is None
    assert rows["commitment"].bar == _bar("choice_hold", 0.7)


async def test_commitment_intake_without_settings_has_null_bars():
    rows = _by_id(await _write(_memory_config(intake=_intake(), settings=None)))
    assert all(r.bar is None for r in rows.values())
    assert rows["commitment"].surface == "commitment_intake"


async def test_commitment_intake_reads_settings_on_each_turn():
    config = _memory_config(intake=_intake(), settings=_settings(**_INTAKE_BARS))
    first = _by_id(await _write(config))
    config["configurable"]["settings"] = _settings(
        **{**_INTAKE_BARS, "choice_hold": 0.9}
    )
    second = _by_id(await _write(config))
    assert first["commitment"].bar.value == 0.7
    assert second["commitment"].bar.value == 0.9


async def test_fact_fallback_rows_have_fact_judge_surface_and_no_bar():
    admission = FactAdmission(
        facts=[],
        path="system_one",
        judgment=SystemOneResult(
            answers={"family": _choice("preference"), "biography": _noul()}, **OK
        ),
        question_ids=("family", "biography"),
        consumed=frozenset({"family"}),
    )

    async def extractor(_cfg, **_kw):
        return admission

    rows = await _write(_memory_config(extractor=extractor))
    assert {r.surface for r in rows} == {"fact_judge"}
    assert all(r.bar is None for r in rows)
