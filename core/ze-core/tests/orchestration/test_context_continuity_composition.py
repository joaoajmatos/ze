"""FR-012 — compaction (write_memory) and resume recap (fetch_context) must both
apply on the same turn without either discarding the other's output when their
partial state dicts are merged, as LangGraph does across sequential node returns."""

import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_agents.types import AgentContext, AgentResult
from ze_memory.types import Entity, MemoryContext, SessionSummary

from ze_core.orchestration.nodes.context import fetch_context
from ze_core.orchestration.nodes.memory import write_memory


def _memory_store() -> MagicMock:
    entity = Entity(id=uuid4(), entity_type="topic", canonical_name="renewal")
    store = AsyncMock()
    store.retrieve = AsyncMock(return_value=MemoryContext(entities=[entity]))
    store.get_session_summary = AsyncMock(
        return_value=SessionSummary(
            id=uuid4(),
            session_id="s1",
            summary="Discussed the passport renewal.",
            episode_count=3,
            last_turn_at=None,
            created_at=None,
            summary_updated_at=None,
        )
    )
    store.write_episode = AsyncMock()
    store.propose_facts = AsyncMock()
    return store


def _embedder() -> MagicMock:
    embedder = MagicMock()
    embedder.encode = MagicMock(return_value=[0.1, 0.2])
    return embedder


async def test_compaction_and_resume_recap_compose_on_same_turn():
    memory_store = _memory_store()
    embedder = _embedder()

    # A big prior history: long enough to (a) exceed the resume-recap inactivity
    # gap and (b) exceed 70% of the (unknown-model → default) context window once
    # write_memory appends this turn's exchange.
    big_content = "x" * 100_000
    prior_messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": big_content if i == 0 else f"m{i}"}
        for i in range(9)
    ]

    ctx_state = {
        "session_id": "s1",
        "prompt": "any update?",
        "envelope": None,
        "messages": prior_messages,
        "last_active_at": time.time() - (31 * 60),
        "memory_context": None,
        "input_modality": "text",
    }
    fetch_config = {
        "configurable": {
            "memory_store": memory_store,
            "embedder": embedder,
            "settings": None,
            "persona_store": None,
            "person_store": None,
            "loop_surfacer": None,
            "goal_store": None,
            "workflow_store": None,
        }
    }
    fetch_result = await fetch_context(ctx_state, fetch_config)
    agent_context: AgentContext = fetch_result["agent_context"]
    agent_context.model = "unknown/model"  # forces DEFAULT_CONTEXT_WINDOW_TOKENS

    assert fetch_result["resume_recap_applied"] is True
    assert agent_context.resume_recap is not None

    client = AsyncMock()
    client.complete = AsyncMock(return_value="condensed summary")
    write_state = {
        "session_id": "s1",
        "agent_context": agent_context,
        "agent_result": AgentResult(agent="companion", response="Still open, I'll follow up."),
        "subtask_results": [],
        "messages": prior_messages,
        "input_modality": "text",
    }
    write_config = {
        "configurable": {
            "memory_store": memory_store,
            "embedder": embedder,
            "thread_id": "s1",
            "openrouter_client": client,
            "settings": None,
            "fact_extractor": None,
        }
    }
    write_result = await write_memory(write_state, write_config)

    # Merge as the graph would across sequential partial-state returns for this turn.
    merged = {**fetch_result, **write_result}

    assert merged["resume_recap_applied"] is True
    assert merged["compaction_span"] is not None
    assert merged["agent_context"].resume_recap is not None


async def test_compaction_llm_failure_end_to_end_turn_still_completes():
    """quickstart.md Scenario 4 / FR-010 — closes the loop past the unit-level T007d
    coverage by driving the same failure through the real write_memory entrypoint."""
    memory_store = _memory_store()
    big_content = "x" * 100_000
    prior_messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": big_content if i == 0 else f"m{i}"}
        for i in range(9)
    ]
    ctx = AgentContext(
        session_id="s1",
        prompt="new message",
        intent="read",
        memory=MemoryContext(),
        messages=[],
        model="unknown/model",
    )
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=RuntimeError("upstream timeout"))
    state = {
        "session_id": "s1",
        "agent_context": ctx,
        "agent_result": AgentResult(agent="companion", response="ok"),
        "subtask_results": [],
        "messages": prior_messages,
        "input_modality": "text",
    }
    config = {
        "configurable": {
            "memory_store": memory_store,
            "embedder": _embedder(),
            "thread_id": "s1",
            "openrouter_client": client,
            "settings": None,
            "fact_extractor": None,
        }
    }
    result = await write_memory(state, config)  # must not raise
    assert result["compaction_span"] is None
    assert len(result["messages"]) <= 10


async def test_unknown_model_end_to_end_uses_default_context_window_no_error():
    """quickstart.md Scenario 5 / FR-005 — a model absent from MODEL_CONTEXT_WINDOWS
    still lets the turn proceed via get_context_window's fallback."""
    memory_store = _memory_store()
    ctx = AgentContext(
        session_id="s1",
        prompt="hello",
        intent="read",
        memory=MemoryContext(),
        messages=[],
        model="some-provider/does-not-exist",
    )
    state = {
        "session_id": "s1",
        "agent_context": ctx,
        "agent_result": AgentResult(agent="companion", response="hi there"),
        "subtask_results": [],
        "messages": [],
        "input_modality": "text",
    }
    config = {
        "configurable": {
            "memory_store": memory_store,
            "embedder": _embedder(),
            "thread_id": "s1",
            "openrouter_client": AsyncMock(),
            "settings": None,
            "fact_extractor": None,
        }
    }
    result = await write_memory(state, config)  # must not raise
    assert result["compaction_span"] is None
    assert result["messages"][-1] == {"role": "assistant", "content": "hi there"}
