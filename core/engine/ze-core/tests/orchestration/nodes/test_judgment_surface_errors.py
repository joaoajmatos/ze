"""A raised or timed-out System One call still shows on the trace (phase 202, US1)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

from ze_agents.judgment import Judgment, SurfaceConfig, judge, reset_surface_warnings
from ze_agents.registry import clear_registry
from ze_agents.system_one import SystemOneResult
from ze_agents.types import AgentContext, AgentResult
from ze_core.conversation.messages.types import MessageTrace
from ze_core.orchestration.nodes.memory import write_memory
from ze_core.orchestration.nodes.routing import embed_route
from ze_core.orchestration.nodes.skills import match_skills
from ze_core.orchestration.nodes.tier import choose_tier
from ze_core.routing.judge import RoutingSurfaceConfig
from ze_core.routing.router import EmbeddingRouter
from ze_core.routing.tier import (
    Q_DEEP,
    ComplexitySurfaceConfig,
    TierJudge,
)
from ze_core.routing.types import RouterConfig, RoutingEnvelope, SubTask
from ze_memory.types import FactAdmission, MemoryContext
from ze_skills.judge import SkillsSurfaceConfig
from ze_skills.matching import SkillMatcher
from ze_skills.types import Skill, SkillSource, SkillStatus

from tests.support.routing import (
    FakeSystemOneClient,
    cosine_embedder,
    register_agent,
)

ROUTING = RoutingSurfaceConfig(
    enabled=True, choice_trust=0.5, multi_specialist_hold=0.5, shortlist_k=3
)
SKILLS = SkillsSurfaceConfig(
    enabled=True,
    choice_trust=0.75,
    needs_skill_hold=0.6,
    shortlist_k=5,
    shortlist_floor=0.35,
)
COMPLEXITY = ComplexitySurfaceConfig(enabled=True, simple_max=0.4)

TIMEOUT = SystemOneResult(outcome="skip", skip_reason="timeout")


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    reset_surface_warnings()
    yield
    clear_registry()


def _rows(rows) -> dict:
    return {r.question_id: r for r in rows}


def _bar(row) -> tuple[str, float] | None:
    return None if row.bar is None else (row.bar.name, row.bar.value)


# ── routing ──────────────────────────────────────────────────────────────────


def _router(client, surface=ROUTING) -> EmbeddingRouter:
    for name in ("calendar", "messenger", "research"):
        register_agent(name)
    return EmbeddingRouter(
        cosine_embedder({"calendar": 0.84, "messenger": 0.50, "research": 0.45}),
        AsyncMock(),
        routing_store=None,
        config=RouterConfig(),
        system_one_client=client,
        surface=surface,
    )


async def _embed(router) -> dict:
    return await embed_route(
        {"session_id": "s1", "prompt": "what is on my calendar"},
        {"configurable": {"router": router}},
    )


async def test_routing_error_writes_a_row_per_question_with_the_bars():
    client = FakeSystemOneClient(error=RuntimeError("boom"))
    out = await _embed(_router(client))
    rows = _rows(out["judgments"])
    assert set(rows) == {"agent", "multi_specialist"}
    for row in rows.values():
        assert row.surface == "routing"
        assert row.skip_reason == "error"
    assert _bar(rows["agent"]) == ("choice_trust", 0.5)
    assert _bar(rows["multi_specialist"]) == ("multi_specialist_hold", 0.5)
    assert out["envelope"].judgment.skip_reason == "error"


async def test_routing_timeout_keeps_the_client_reason_on_every_row():
    out = await _embed(_router(FakeSystemOneClient(TIMEOUT)))
    assert {r.skip_reason for r in out["judgments"]} == {"timeout"}
    assert {r.question_id for r in out["judgments"]} == {"agent", "multi_specialist"}


async def test_routing_uncalibrated_surface_makes_no_call_and_no_rows():
    client = FakeSystemOneClient(error=RuntimeError("boom"))
    surface = RoutingSurfaceConfig(enabled=True, choice_trust=0.5)
    out = await _embed(_router(client, surface))
    assert client.calls == []
    assert out["judgments"] == []


# ── skills ───────────────────────────────────────────────────────────────────


def _skill(name: str) -> Skill:
    return Skill(
        name=name,
        description="does a thing",
        instructions="Do the thing.",
        source=SkillSource.IMPORTED,
        status=SkillStatus.ACTIVE,
        id=uuid4(),
    )


class _SimEmbedder:
    def encode_query(self, text, **kw):
        return np.array([1.0, 0.0], dtype=np.float32)

    def encode_passage(self, texts, **kw):
        return np.stack(
            [np.array([0.7, math.sqrt(1 - 0.49)], dtype=np.float32) for _ in texts]
        )


def _matcher(client, surface=SKILLS) -> SkillMatcher:
    store = AsyncMock()
    store.list_active = AsyncMock(return_value=[_skill("Email Tone")])
    return SkillMatcher(
        store=store,
        embedder=_SimEmbedder(),
        match_threshold=0.5,
        system_one_client=client,
        surface=surface,
    )


async def _skills(matcher) -> dict:
    state = {
        "prompt": "write an email",
        "image_caption": None,
        "agent_context": AgentContext(session_id="s1", prompt="write an email"),
    }
    return await match_skills(state, {"configurable": {"skill_matcher": matcher}})


async def test_skills_error_writes_a_row_per_question_with_the_bars():
    out = await _skills(_matcher(FakeSystemOneClient(error=RuntimeError("boom"))))
    rows = _rows(out["judgments"])
    assert set(rows) == {"skill", "needs_skill"}
    for row in rows.values():
        assert row.surface == "skills"
        assert row.skip_reason == "error"
    assert _bar(rows["skill"]) == ("choice_trust", 0.75)
    assert _bar(rows["needs_skill"]) == ("needs_skill_hold", 0.6)


async def test_skills_uncalibrated_surface_makes_no_call_and_no_rows():
    client = FakeSystemOneClient(error=RuntimeError("boom"))
    surface = SkillsSurfaceConfig(enabled=True, choice_trust=0.75)
    out = await _skills(_matcher(client, surface))
    assert client.calls == []
    assert "judgments" not in out


# ── complexity ───────────────────────────────────────────────────────────────


async def _tier(client) -> tuple[dict, RoutingEnvelope]:
    register_agent("t202", model="full-m", model_simple="light-m")
    envelope = RoutingEnvelope(
        primary_agent="t202",
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=False,
        subtasks=[SubTask(agent="t202", prompt="thanks", model="full-m")],
        requires_synthesis=False,
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
    judge_ = TierJudge(client, COMPLEXITY, {})
    return await choose_tier(state, {"configurable": {"tier_judge": judge_}}), envelope


async def test_tier_error_writes_one_row_and_keeps_the_full_model():
    out, _ = await _tier(FakeSystemOneClient(error=RuntimeError("boom")))
    [row] = out["judgments"]
    assert row.question_id == Q_DEEP
    assert row.surface == "complexity"
    assert row.skip_reason == "error"
    assert _bar(row) == ("simple_max", 0.4)
    assert out["tier"].tier == "full"
    assert "envelope" not in out


async def test_tier_timeout_keeps_the_client_reason():
    out, _ = await _tier(FakeSystemOneClient(TIMEOUT))
    [row] = out["judgments"]
    assert row.skip_reason == "timeout"


# ── commitment intake ────────────────────────────────────────────────────────

_INTAKE_QUESTIONS = {
    qid: SimpleNamespace(type=kind)
    for qid, kind in (
        ("commitment", "choice"),
        ("family", "choice"),
        ("biography", "noul"),
        ("is_open_concern", "noul"),
        ("explicit_declaration", "noul"),
        ("resolves_existing", "noul"),
    )
}
_INTAKE_BARS = {
    "commitment": ("choice_hold", 0.7),
    "family": ("family_hold", 0.7),
    "biography": ("biography_hold", 0.55),
    "is_open_concern": ("loop_hold", 0.6),
    "explicit_declaration": ("explicit_hold", 0.95),
    "resolves_existing": ("resolves_hold", 0.8),
}


@dataclass(frozen=True)
class _IntakeCfg(SurfaceConfig):
    choice_hold: float | None = 0.7
    family_hold: float | None = 0.7
    biography_hold: float | None = 0.55
    loop_hold: float | None = 0.6
    explicit_hold: float | None = 0.95
    resolves_hold: float | None = 0.8

    SURFACE: ClassVar[str] = "commitment_intake"
    BARS: ClassVar[dict[str, str]] = {
        bar: qid for qid, (bar, _) in _INTAKE_BARS.items()
    }


async def _raised_intake_judgment() -> Judgment:
    client = FakeSystemOneClient(error=RuntimeError("boom"))
    record, _ = await judge(
        client,
        _IntakeCfg(enabled=True),
        {"user": "hi"},
        _INTAKE_QUESTIONS,
        decide=lambda result: result,
        read=lambda _decision: SimpleNamespace(
            consumed=frozenset(), unused_reason=None
        ),
    )
    return record


async def test_intake_error_writes_six_rows_and_the_outcome_row():
    record = await _raised_intake_judgment()
    intake = SimpleNamespace(
        outcome=SimpleNamespace(kind="fallback", reason="error", link_kind=None),
        fact=FactAdmission(path="haiku"),
        loop=None,
        links=(),
        judgment=record,
    )

    async def _call(_cfg, **_kw):
        return intake

    store = AsyncMock()
    embedder = MagicMock()
    embedder.encode_passage = embedder.encode_query = MagicMock(return_value=[0.1])
    config = {
        "configurable": {
            "memory_store": store,
            "embedder": embedder,
            "thread_id": "s1",
            "commitment_intake": _call,
        }
    }
    state = {
        "session_id": "s1",
        "agent_context": AgentContext(
            session_id="s1", prompt="hi", memory=MemoryContext()
        ),
        "agent_result": AgentResult(agent="companion", response="Hello."),
        "subtask_results": [],
        "messages": [],
        "input_modality": "text",
        "message_trace": MessageTrace(
            agent="companion",
            routing_method="embedding",
            confidence=0.9,
            score_gap=0.3,
            is_compound=False,
            subtasks=[],
        ),
    }
    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ):
        out = await write_memory(state, config)
    rows = _rows(out["message_trace"].judgments)
    assert set(rows) == {*_INTAKE_QUESTIONS, "intake_outcome"}
    for qid, bar in _INTAKE_BARS.items():
        assert rows[qid].surface == "commitment_intake"
        assert rows[qid].skip_reason == "error"
        assert _bar(rows[qid]) == bar
    assert rows["intake_outcome"].answer == "fallback:error"
    assert rows["intake_outcome"].skip_reason == "error"
