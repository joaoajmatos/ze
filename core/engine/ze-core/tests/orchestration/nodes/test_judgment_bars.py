"""Trace judgment rows carry the surface and the bar in force, from the record alone (187b, 202)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

from ze_agents.judgment import SurfaceConfig, judge, reset_surface_warnings
from ze_agents.registry import clear_registry
from ze_agents.system_one import SystemOneAnswer, SystemOneQuestion, SystemOneResult
from ze_agents.types import AgentContext, AgentResult
from ze_core.conversation.messages.types import JudgmentBar, MessageTrace
from ze_core.orchestration.nodes.memory import write_memory
from ze_core.orchestration.nodes.routing import embed_route
from ze_core.orchestration.nodes.skills import match_skills
from ze_core.orchestration.nodes.tier import choose_tier
from ze_core.routing.judge import RoutingSurfaceConfig
from ze_core.routing.router import EmbeddingRouter
from ze_core.routing.tier import Q_DEEP, ComplexitySurfaceConfig, TierJudge
from ze_core.routing.types import RouterConfig, RoutingEnvelope, SubTask
from ze_memory.types import Fact, FactAdmission, MemoryContext
from ze_skills.judge import SkillsSurfaceConfig
from ze_skills.matching import SkillMatcher
from ze_skills.types import Skill, SkillSource, SkillStatus

from tests.support.routing import (
    FakeSystemOneClient,
    cosine_embedder,
    ok_result,
    register_agent,
)

OK = dict(outcome="ok", model="jev", input_tokens=10, latency_ms=5)


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    reset_surface_warnings()
    yield
    clear_registry()


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


async def _route(surface: RoutingSurfaceConfig) -> list:
    clear_registry()
    for name in ("calendar", "messenger", "research"):
        register_agent(name)
    router = EmbeddingRouter(
        cosine_embedder({"calendar": 0.84, "messenger": 0.50, "research": 0.45}),
        AsyncMock(),
        routing_store=None,
        config=RouterConfig(),
        system_one_client=FakeSystemOneClient(ok_result(choice="calendar", noul=0.1)),
        surface=surface,
    )
    out = await embed_route(
        {"session_id": "s1", "prompt": "what is on my calendar"},
        {"configurable": {"router": router}},
    )
    return out["judgments"]


async def test_routing_rows_carry_surface_and_bars():
    rows = _by_id(
        await _route(
            RoutingSurfaceConfig(
                enabled=True, choice_trust=0.5, multi_specialist_hold=0.4
            )
        )
    )
    assert {r.surface for r in rows.values()} == {"routing"}
    assert rows["agent"].bar == _bar("choice_trust", 0.5)
    assert rows["multi_specialist"].bar == _bar("multi_specialist_hold", 0.4)


async def test_routing_reads_the_surface_in_force_each_turn():
    first = _by_id(
        await _route(
            RoutingSurfaceConfig(
                enabled=True, choice_trust=0.5, multi_specialist_hold=0.4
            )
        )
    )
    second = _by_id(
        await _route(
            RoutingSurfaceConfig(
                enabled=True, choice_trust=0.8, multi_specialist_hold=0.4
            )
        )
    )
    assert first["agent"].bar.value == 0.5
    assert second["agent"].bar.value == 0.8


# ── skills ───────────────────────────────────────────────────────────────────


class _SimEmbedder:
    def encode_query(self, text, **kw):
        return np.array([1.0, 0.0], dtype=np.float32)

    def encode_passage(self, texts, **kw):
        return np.stack(
            [np.array([0.7, math.sqrt(1 - 0.49)], dtype=np.float32) for _ in texts]
        )


async def _skills(surface: SkillsSurfaceConfig) -> list:
    skill = Skill(
        name="Email Tone",
        description="does a thing",
        instructions="Do the thing.",
        source=SkillSource.IMPORTED,
        status=SkillStatus.ACTIVE,
        id=uuid4(),
    )
    store = AsyncMock()
    store.list_active = AsyncMock(return_value=[skill])
    answers = {"skill": _choice("email-tone"), "needs_skill": _noul(0.9)}
    matcher = SkillMatcher(
        store=store,
        embedder=_SimEmbedder(),
        match_threshold=0.5,
        system_one_client=FakeSystemOneClient(SystemOneResult(answers=answers, **OK)),
        surface=surface,
    )
    state = {
        "prompt": "write an email",
        "image_caption": None,
        "agent_context": AgentContext(session_id="s1", prompt="write an email"),
    }
    out = await match_skills(state, {"configurable": {"skill_matcher": matcher}})
    return out["judgments"]


async def test_skills_rows_carry_surface_and_bars():
    rows = _by_id(
        await _skills(
            SkillsSurfaceConfig(enabled=True, choice_trust=0.75, needs_skill_hold=0.6)
        )
    )
    assert {r.surface for r in rows.values()} == {"skills"}
    assert rows["skill"].bar == _bar("choice_trust", 0.75)
    assert rows["needs_skill"].bar == _bar("needs_skill_hold", 0.6)


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
    judge_ = TierJudge(
        client, ComplexitySurfaceConfig(enabled=True, simple_max=0.2), {}
    )
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
    out = await choose_tier(state, {"configurable": {"tier_judge": judge_}})
    [row] = out["judgments"]
    assert row.surface == "complexity"
    assert row.bar == _bar("simple_max", 0.2)


# ── commitment intake ────────────────────────────────────────────────────────

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
_INTAKE_QUESTIONS = {
    qid: SystemOneQuestion(type=kind, instructions=qid)
    for qid, kind in (
        ("commitment", "choice"),
        ("family", "choice"),
        ("biography", "noul"),
        ("is_open_concern", "noul"),
        ("explicit_declaration", "noul"),
        ("resolves_existing", "noul"),
    )
}


@dataclass(frozen=True)
class _IntakeCfg(SurfaceConfig):
    choice_hold: float | None = None
    family_hold: float | None = None
    biography_hold: float | None = None
    loop_hold: float | None = None
    explicit_hold: float | None = None
    resolves_hold: float | None = None

    SURFACE: ClassVar[str] = "commitment_intake"
    BARS: ClassVar[dict[str, str]] = {bar: qid for qid, bar in _INTAKE_IDS.items()}


async def _intake(**bars) -> SimpleNamespace:
    answers = {
        "commitment": _choice("fact"),
        "family": _choice("preference"),
        "biography": _noul(0.9),
        "is_open_concern": _noul(0.1),
        "explicit_declaration": _noul(0.1),
        "resolves_existing": _noul(0.1),
    }
    record, _ = await judge(
        FakeSystemOneClient(SystemOneResult(answers=answers, **OK)),
        _IntakeCfg(enabled=True, **bars),
        {"user": "I prefer aisle seats"},
        _INTAKE_QUESTIONS,
        decide=lambda result: result,
        read=lambda _decision: SimpleNamespace(
            consumed=frozenset({"commitment", "family", "biography"}),
            unused_reason=None,
        ),
    )
    return SimpleNamespace(
        outcome=SimpleNamespace(kind="persist_fact", reason="family", link_kind=None),
        fact=FactAdmission(
            facts=[Fact(predicate="preference", value="aisle seats")], path="system_one"
        ),
        loop=None,
        links=(),
        judgment=record,
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


def _memory_config(intake) -> dict:
    store = AsyncMock()
    store.write_episode = AsyncMock()
    embedder = MagicMock()
    embedder.encode_passage = embedder.encode_query = MagicMock(return_value=[0.1])

    async def _call(_cfg, **_kw):
        return intake

    return {
        "configurable": {
            "memory_store": store,
            "embedder": embedder,
            "thread_id": "s1",
            "commitment_intake": _call,
        }
    }


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


async def _write(intake) -> list:
    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ):
        out = await write_memory(_memory_state(), _memory_config(intake))
    return out["message_trace"].judgments


async def test_commitment_intake_rows_carry_the_six_holds():
    rows = _by_id(await _write(await _intake(**_INTAKE_BARS)))
    for qid, bar_name in _INTAKE_IDS.items():
        assert rows[qid].surface == "commitment_intake"
        assert rows[qid].bar == _bar(bar_name, _INTAKE_BARS[bar_name]), qid


async def test_commitment_intake_outcome_row_has_surface_and_no_bar():
    rows = _by_id(await _write(await _intake(**_INTAKE_BARS)))
    assert rows["intake_outcome"].surface == "commitment_intake"
    assert rows["intake_outcome"].bar is None


async def test_commitment_intake_unset_bar_is_null():
    partial = {k: v for k, v in _INTAKE_BARS.items() if k != "loop_hold"}
    rows = _by_id(await _write(await _intake(**partial)))
    assert rows["is_open_concern"].surface == "commitment_intake"
    assert rows["is_open_concern"].bar is None
    assert rows["commitment"].bar == _bar("choice_hold", 0.7)


async def test_commitment_intake_reads_the_surface_on_each_turn():
    first = _by_id(await _write(await _intake(**_INTAKE_BARS)))
    second = _by_id(await _write(await _intake(**{**_INTAKE_BARS, "choice_hold": 0.9})))
    assert first["commitment"].bar.value == 0.7
    assert second["commitment"].bar.value == 0.9
