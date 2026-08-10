import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_automation.goals.types import Goal, GoalStatus
from ze_automation.workflow.types import Workflow, WorkflowExecution
from ze_memory.types import Entity, MemoryContext, SessionSummary

from ze_core.orchestration.nodes.context import fetch_context


def _make_store(memory_context=None) -> MagicMock:
    store = AsyncMock()
    store.retrieve = AsyncMock(return_value=memory_context or MemoryContext())
    store.get_session_summary = AsyncMock(return_value=None)
    return store


def _make_embedder() -> MagicMock:
    embedder = MagicMock()
    embedder.encode = MagicMock(return_value=[0.1, 0.2])
    return embedder


def _config(
    store=None,
    embedder=None,
    settings=None,
    loop_surfacer=None,
    goal_store=None,
    workflow_store=None,
) -> dict:
    return {
        "configurable": {
            "memory_store": store or _make_store(),
            "embedder": embedder or _make_embedder(),
            "settings": settings,
            "persona_store": None,
            "person_store": None,
            "loop_surfacer": loop_surfacer,
            "goal_store": goal_store,
            "workflow_store": workflow_store,
        }
    }


def _state(session_id="s1", prompt="hi", messages=None, last_active_at=None) -> dict:
    return {
        "session_id": session_id,
        "prompt": prompt,
        "envelope": None,
        "messages": messages or [],
        "last_active_at": last_active_at,
        "memory_context": None,
    }


class TestFetchContextGapCheckRegression:
    async def test_gap_under_threshold_history_unchanged_no_recap(self):
        existing = [{"role": "user", "content": "earlier"}]
        state = _state(messages=existing, last_active_at=time.time() - 5)
        result = await fetch_context(state, _config())
        assert result["agent_context"].messages[:-1] == existing
        assert result["agent_context"].resume_recap is None
        assert result["resume_recap_applied"] is False

    async def test_gap_over_threshold_no_outstanding_state_blanks_history(self):
        state = _state(
            messages=[{"role": "user", "content": "old"}],
            last_active_at=time.time() - (31 * 60),
        )
        result = await fetch_context(state, _config())
        # history is blanked (unchanged from today) — only this turn's message remains
        assert len(result["agent_context"].messages) == 1
        assert result["agent_context"].resume_recap is None
        assert result["resume_recap_applied"] is False


class TestFetchContextResumeRecap:
    async def test_gap_over_threshold_with_outstanding_state_builds_recap(self):
        entity = Entity(id=uuid4(), entity_type="topic", canonical_name="passport renewal")
        store = _make_store(memory_context=MemoryContext(entities=[entity]))
        store.get_session_summary = AsyncMock(
            return_value=SessionSummary(
                id=uuid4(),
                session_id="s1",
                summary="We discussed the migration plan.",
                episode_count=5,
                last_turn_at=None,
                created_at=None,
                summary_updated_at=None,
            )
        )

        surfacer = AsyncMock()
        mention = MagicMock()
        mention.mention_text = 'It looks like "Renew passport" may still be open'
        surfacer.inline_candidates = AsyncMock(return_value=[mention])

        goal_store = AsyncMock()
        goal_store.list_active = AsyncMock(
            return_value=[
                Goal(
                    title="Ship v2",
                    objective="Launch the v2 API",
                    success_condition="v2 is live",
                    status=GoalStatus.ACTIVE,
                )
            ]
        )

        wf_id = uuid4()
        workflow_store = AsyncMock()
        workflow_store.list_all = AsyncMock(
            return_value=[
                Workflow(
                    id=wf_id,
                    name="daily-briefing",
                    description="",
                    steps=[],
                    schedule=None,
                    enabled=True,
                    last_run_at=None,
                    next_run_at=None,
                    created_at=None,
                    updated_at=None,
                )
            ]
        )
        workflow_store.list_executions = AsyncMock(
            return_value=[WorkflowExecution(id=uuid4(), workflow_id=wf_id, status="running")]
        )

        state = _state(
            messages=[{"role": "user", "content": "old"}],
            last_active_at=time.time() - (31 * 60),
        )
        result = await fetch_context(
            state,
            _config(
                store=store,
                loop_surfacer=surfacer,
                goal_store=goal_store,
                workflow_store=workflow_store,
            ),
        )

        recap = result["agent_context"].resume_recap
        assert recap is not None
        assert "migration plan" in recap
        assert "Renew passport" in recap
        assert "Ship v2" in recap
        assert "daily-briefing" in recap
        assert result["resume_recap_applied"] is True

    async def test_gap_under_threshold_with_outstanding_state_recap_stays_none(self):
        goal_store = AsyncMock()
        goal_store.list_active = AsyncMock(
            return_value=[
                Goal(
                    title="Ship v2",
                    objective="Launch the v2 API",
                    success_condition="v2 is live",
                    status=GoalStatus.ACTIVE,
                )
            ]
        )
        state = _state(
            messages=[{"role": "user", "content": "old"}],
            last_active_at=time.time() - 5,
        )
        result = await fetch_context(state, _config(goal_store=goal_store))
        assert result["agent_context"].resume_recap is None
        assert result["resume_recap_applied"] is False
