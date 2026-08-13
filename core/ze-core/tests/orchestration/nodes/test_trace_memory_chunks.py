"""Tests for memory-chunk trace extraction (phase 106, User Story 1)."""

from __future__ import annotations

from types import SimpleNamespace

from ze_core.conversation.messages.types import CompactionTrace
from ze_core.orchestration.nodes.trace import _extract_memory_chunks, record_trace


def _envelope():
    return SimpleNamespace(
        primary_agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
    )


def _fact(relevance_score=None, confidence=1.0):
    return SimpleNamespace(
        predicate="likes",
        value="coffee",
        relevance_score=relevance_score,
        confidence=confidence,
    )


def _episode(relevance_score=None):
    return SimpleNamespace(
        summary="a chat", response="hi", relevance_score=relevance_score
    )


def test_extract_memory_chunks_sets_score_from_relevance_score_not_confidence():
    ctx = SimpleNamespace(
        facts=[_fact(relevance_score=0.82, confidence=1.0)], episodes=[]
    )
    chunks = _extract_memory_chunks(ctx)
    assert len(chunks) == 1
    assert chunks[0].score == 0.82
    assert chunks[0].extraction_confidence == 1.0


def test_extract_memory_chunks_extraction_confidence_kept_separate_from_score():
    ctx = SimpleNamespace(
        facts=[_fact(relevance_score=0.1, confidence=0.99)], episodes=[]
    )
    chunks = _extract_memory_chunks(ctx)
    assert chunks[0].score == 0.1
    assert chunks[0].extraction_confidence == 0.99
    assert chunks[0].score != chunks[0].extraction_confidence


def test_extract_memory_chunks_missing_relevance_score_defaults_to_zero():
    ctx = SimpleNamespace(facts=[_fact(relevance_score=None)], episodes=[])
    chunks = _extract_memory_chunks(ctx)
    assert chunks[0].score == 0.0


def test_extract_memory_chunks_episode_score_from_relevance_score():
    ctx = SimpleNamespace(facts=[], episodes=[_episode(relevance_score=0.55)])
    chunks = _extract_memory_chunks(ctx)
    assert chunks[0].score == 0.55
    assert chunks[0].source == "episode"


def test_extract_memory_chunks_empty_context_returns_empty_list():
    ctx = SimpleNamespace(facts=[], episodes=[])
    assert _extract_memory_chunks(ctx) == []


def test_extract_memory_chunks_none_context_returns_empty_list():
    assert _extract_memory_chunks(None) == []


async def test_record_trace_produces_empty_memory_chunks_not_missing_trace():
    envelope = SimpleNamespace(
        primary_agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
    )
    state = {
        "envelope": envelope,
        "agent_result": None,
        "memory_context": SimpleNamespace(facts=[], episodes=[]),
    }

    result = await record_trace(state, config={})

    trace = result["message_trace"]
    assert trace is not None
    assert trace.memory_chunks == []


async def test_record_trace_compaction_span_none_leaves_trace_compaction_none():
    state = {
        "envelope": _envelope(),
        "agent_result": None,
        "memory_context": None,
        "compaction_span": None,
    }
    result = await record_trace(state, config={})
    assert result["message_trace"].compaction is None


async def test_record_trace_compaction_span_populates_compaction_trace():
    state = {
        "envelope": _envelope(),
        "agent_result": None,
        "memory_context": None,
        "compaction_span": (0, 7),
    }
    result = await record_trace(state, config={})
    assert result["message_trace"].compaction == CompactionTrace(
        span_start=0, span_end=7
    )


async def test_record_trace_resume_recap_applied_passthrough_true():
    state = {
        "envelope": _envelope(),
        "agent_result": None,
        "memory_context": None,
        "resume_recap_applied": True,
    }
    result = await record_trace(state, config={})
    assert result["message_trace"].resume_recap_applied is True


async def test_record_trace_resume_recap_applied_defaults_false_when_absent():
    state = {
        "envelope": _envelope(),
        "agent_result": None,
        "memory_context": None,
    }
    result = await record_trace(state, config={})
    assert result["message_trace"].resume_recap_applied is False


async def test_record_trace_compaction_and_resume_recap_compose_in_same_trace():
    """FR-011/FR-012 — both fields populate independently on the same turn."""
    state = {
        "envelope": _envelope(),
        "agent_result": None,
        "memory_context": None,
        "compaction_span": (0, 12),
        "resume_recap_applied": True,
    }
    result = await record_trace(state, config={})
    trace = result["message_trace"]
    assert trace.compaction == CompactionTrace(span_start=0, span_end=12)
    assert trace.resume_recap_applied is True


# ── skills_used (Phase 114, User Story 2) ───────────────────────────────────────


def _skill_match(
    name="Pirate Speak", source="imported", trigger="automatic", similarity=0.7
):
    skill = SimpleNamespace(
        id="skill-1", name=name, source=SimpleNamespace(value=source)
    )
    return SimpleNamespace(
        skill=skill, trigger=SimpleNamespace(value=trigger), similarity=similarity
    )


async def test_record_trace_skills_used_empty_when_no_skill_matched():
    state = {"envelope": _envelope(), "agent_result": None, "memory_context": None}
    result = await record_trace(state, config={})
    assert result["message_trace"].skills_used == []


async def test_record_trace_skills_used_populated_from_skill_matches():
    state = {
        "envelope": _envelope(),
        "agent_result": None,
        "memory_context": None,
        "skill_matches": [_skill_match()],
    }
    result = await record_trace(state, config={})
    used = result["message_trace"].skills_used
    assert len(used) == 1
    assert used[0].skill_id == "skill-1"
    assert used[0].name == "Pirate Speak"
    assert used[0].source == "imported"
    assert used[0].trigger == "automatic"
    assert used[0].similarity == 0.7


async def test_record_trace_skills_used_explicit_trigger_has_no_similarity():
    state = {
        "envelope": _envelope(),
        "agent_result": None,
        "memory_context": None,
        "skill_matches": [_skill_match(trigger="explicit", similarity=None)],
    }
    result = await record_trace(state, config={})
    used = result["message_trace"].skills_used
    assert used[0].trigger == "explicit"
    assert used[0].similarity is None
