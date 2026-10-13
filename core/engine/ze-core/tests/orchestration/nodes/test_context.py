import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_agents.types import AgentResult
from ze_automation.workflow.types import Workflow, WorkflowExecution
from ze_memory.types import Entity, MemoryContext, SessionSummary

from ze_core.orchestration.nodes.context import fetch_context
from ze_core.orchestration.nodes.loop_surfacing import surface_loops


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
    turn_surfacer=None,
    workflow_store=None,
) -> dict:
    return {
        "configurable": {
            "memory_store": store or _make_store(),
            "embedder": embedder or _make_embedder(),
            "settings": settings,
            "persona_store": None,
            "person_store": None,
            "turn_surfacer": turn_surfacer,
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


def _mention(title: str, *, kind: str = "goal") -> SimpleNamespace:
    return SimpleNamespace(
        source_kind=kind,
        source_id=uuid4(),
        title=title,
        mention_text=f'It looks like "{title}" may still be open',
    )


def _surfacer(
    mentions=None, *, global_query: bool = False, error: Exception | None = None
):
    s = AsyncMock()
    if error is not None:
        s.recap_mentions = AsyncMock(side_effect=error)
    else:
        s.recap_mentions = AsyncMock(return_value=mentions or [])
    s.inline_mentions = AsyncMock(return_value=mentions or [])
    s.resume_loop_offers = AsyncMock(return_value=[])
    s.is_global_open_query = MagicMock(return_value=global_query)
    return s


def _ranked_mentions() -> list[SimpleNamespace]:
    return [
        _mention("Ship v2", kind="goal"),
        _mention("Renew passport", kind="loop"),
    ]


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
        assert len(result["agent_context"].messages) == 1
        assert result["agent_context"].resume_recap is None
        assert result["resume_recap_applied"] is False


class TestFetchContextResumeRecap:
    async def test_gap_over_threshold_lists_open_items_in_rank_order(self):
        store = _make_store()
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

        mentions = _ranked_mentions()
        surfacer = _surfacer(mentions)

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
            return_value=[
                WorkflowExecution(id=uuid4(), workflow_id=wf_id, status="running")
            ]
        )

        state = _state(
            messages=[{"role": "user", "content": "old"}],
            last_active_at=time.time() - (31 * 60),
        )
        result = await fetch_context(
            state,
            _config(
                store=store,
                turn_surfacer=surfacer,
                workflow_store=workflow_store,
            ),
        )

        recap = result["agent_context"].resume_recap
        assert recap is not None
        assert "migration plan" in recap
        assert recap.index("Ship v2") < recap.index("Renew passport")
        assert "daily-briefing" in recap
        assert result["resume_recap_applied"] is True
        surfacer.recap_mentions.assert_awaited_once()

    async def test_gap_under_threshold_with_open_items_recap_stays_none(self):
        surfacer = _surfacer(_ranked_mentions())
        state = _state(
            messages=[{"role": "user", "content": "old"}],
            last_active_at=time.time() - 5,
        )
        result = await fetch_context(state, _config(turn_surfacer=surfacer))
        assert result["agent_context"].resume_recap is None
        assert result["resume_recap_applied"] is False
        surfacer.recap_mentions.assert_not_awaited()

    async def test_missing_turn_surfacer_still_completes_the_turn(self):
        store = _make_store()
        store.get_session_summary = AsyncMock(
            return_value=SessionSummary(
                id=uuid4(),
                session_id="s1",
                summary="Wrapped the last session.",
                episode_count=2,
                last_turn_at=None,
                created_at=None,
                summary_updated_at=None,
            )
        )
        state = _state(last_active_at=time.time() - (31 * 60))
        result = await fetch_context(state, _config(store=store, turn_surfacer=None))
        assert result["agent_context"].resume_recap is not None
        assert "Wrapped the last session" in result["agent_context"].resume_recap
        assert result["resume_recap_applied"] is True

    async def test_turn_surfacer_failure_still_completes_the_turn(self):
        store = _make_store()
        store.get_session_summary = AsyncMock(
            return_value=SessionSummary(
                id=uuid4(),
                session_id="s1",
                summary="Prior chat.",
                episode_count=1,
                last_turn_at=None,
                created_at=None,
                summary_updated_at=None,
            )
        )
        surfacer = _surfacer(error=RuntimeError("rank failed"))
        state = _state(last_active_at=time.time() - (31 * 60))
        result = await fetch_context(
            state, _config(store=store, turn_surfacer=surfacer)
        )
        assert result["agent_context"].resume_recap is not None
        assert "Prior chat" in result["agent_context"].resume_recap
        assert result["resume_recap_applied"] is True


class TestFetchContextWhatsOpen:
    async def test_whats_open_sets_ranked_open_priorities_note(self):
        mentions = _ranked_mentions()
        surfacer = _surfacer(mentions, global_query=True)
        state = _state(prompt="what's open right now")
        result = await fetch_context(state, _config(turn_surfacer=surfacer))

        note = result["agent_context"].open_priorities_note
        assert note is not None
        assert note.index("Ship v2") < note.index("Renew passport")
        assert result["agent_context"].resume_recap is None
        surfacer.recap_mentions.assert_awaited_once()

    async def test_non_open_prompt_does_not_set_note(self):
        surfacer = _surfacer(_ranked_mentions(), global_query=False)
        result = await fetch_context(
            _state(prompt="how's the weather"), _config(turn_surfacer=surfacer)
        )
        assert result["agent_context"].open_priorities_note is None
        surfacer.recap_mentions.assert_not_awaited()

    async def test_whats_open_does_not_also_append_inline_mentions(self):
        mentions = _ranked_mentions()
        surfacer = _surfacer(mentions, global_query=True)
        config = _config(turn_surfacer=surfacer)
        fetch_result = await fetch_context(
            _state(prompt="what's open right now"), config
        )
        assert fetch_result["agent_context"].open_priorities_note is not None

        loop_result = await surface_loops(
            {
                "prompt": "what's open right now",
                "open_items_query": fetch_result["open_items_query"],
                "envelope": None,
                "memory_context": MemoryContext(
                    entities=[
                        Entity(
                            id=uuid4(),
                            entity_type="topic",
                            canonical_name="passport",
                        )
                    ]
                ),
                "components": [],
                "subtask_results": [],
                "agent_result": AgentResult(agent="companion", response="Main answer."),
            },
            config,
        )
        assert loop_result == {}
        surfacer.inline_mentions.assert_not_awaited()


def _offer(title: str) -> SimpleNamespace:
    return SimpleNamespace(loop_id=uuid4(), title=title, provenance="email")


_OFFER_INSTRUCTION = (
    "End your reply with one short question, in the user's language, asking whether "
    "they want you to keep track of these. Do not say they are being tracked."
)


class TestFetchContextLoopOffers:
    async def test_gap_with_offers_renders_block_after_open_items(self):
        offers = [_offer("Switch bank"), _offer("Dentist appointment")]
        surfacer = _surfacer(_ranked_mentions())
        surfacer.resume_loop_offers = AsyncMock(return_value=offers)
        state = _state(last_active_at=time.time() - (31 * 60))

        result = await fetch_context(state, _config(turn_surfacer=surfacer))

        recap = result["agent_context"].resume_recap
        assert (
            "Not yet tracked (Ze noticed these; the user has not confirmed them):\n"
            "- Switch bank\n- Dentist appointment\n" + _OFFER_INSTRUCTION
        ) in recap
        assert recap.index("Renew passport") < recap.index("Not yet tracked")
        assert result["loop_offer_ids"] == [str(o.loop_id) for o in offers]
        assert result["resume_recap_applied"] is True

    async def test_offers_alone_still_apply_the_recap(self):
        surfacer = _surfacer([])
        surfacer.resume_loop_offers = AsyncMock(return_value=[_offer("Switch bank")])
        state = _state(last_active_at=time.time() - (31 * 60))

        result = await fetch_context(state, _config(turn_surfacer=surfacer))

        assert result["resume_recap_applied"] is True
        assert "Switch bank" in result["agent_context"].resume_recap

    async def test_no_gap_does_not_ask_for_offers(self):
        surfacer = _surfacer([])
        state = _state(last_active_at=time.time() - 5)

        result = await fetch_context(state, _config(turn_surfacer=surfacer))

        surfacer.resume_loop_offers.assert_not_awaited()
        assert result["loop_offer_ids"] == []

    async def test_retry_mode_does_not_ask_for_offers(self):
        surfacer = _surfacer(_ranked_mentions())
        config = _config(turn_surfacer=surfacer)
        config["configurable"]["retry_mode"] = True
        state = _state(last_active_at=time.time() - (31 * 60))

        result = await fetch_context(state, config)

        surfacer.resume_loop_offers.assert_not_awaited()
        assert result["loop_offer_ids"] == []

    async def test_offer_failure_does_not_break_the_turn(self):
        surfacer = _surfacer(_ranked_mentions())
        surfacer.resume_loop_offers = AsyncMock(side_effect=RuntimeError("db"))
        state = _state(last_active_at=time.time() - (31 * 60))

        result = await fetch_context(state, _config(turn_surfacer=surfacer))

        assert result["loop_offer_ids"] == []
        assert "Not yet tracked" not in result["agent_context"].resume_recap


class TestFetchContextCaps:
    async def test_resume_recap_is_capped_at_five(self):
        surfacer = _surfacer(_ranked_mentions())
        state = _state(last_active_at=time.time() - (31 * 60))

        await fetch_context(state, _config(turn_surfacer=surfacer))

        surfacer.recap_mentions.assert_awaited_once_with(limit=5)

    async def test_open_priorities_note_is_capped_at_ten(self):
        surfacer = _surfacer(_ranked_mentions(), global_query=True)

        await fetch_context(
            _state(prompt="what's open right now"), _config(turn_surfacer=surfacer)
        )

        surfacer.recap_mentions.assert_awaited_once_with(limit=10)


class TestFetchContextOpenQueryFlag:
    async def test_detector_receives_the_prompt_embedding(self):
        surfacer = _surfacer([], global_query=True)
        embedder = _make_embedder()
        embedder.encode = MagicMock(return_value=[0.3, 0.4])

        result = await fetch_context(
            _state(prompt="o que tenho em aberto?"),
            _config(turn_surfacer=surfacer, embedder=embedder),
        )

        surfacer.is_global_open_query.assert_called_once_with([0.3, 0.4])
        assert result["open_items_query"] is True

    async def test_false_when_not_an_open_query(self):
        surfacer = _surfacer(_ranked_mentions(), global_query=False)

        result = await fetch_context(_state(), _config(turn_surfacer=surfacer))

        assert result["open_items_query"] is False
        assert result["agent_context"].open_priorities_note is None

    async def test_false_without_a_surfacer(self):
        result = await fetch_context(_state(), _config())
        assert result["open_items_query"] is False

    async def test_detector_failure_is_false_and_turn_completes(self):
        surfacer = _surfacer(_ranked_mentions())
        surfacer.is_global_open_query = MagicMock(side_effect=RuntimeError("boom"))

        result = await fetch_context(_state(), _config(turn_surfacer=surfacer))

        assert result["open_items_query"] is False
        assert result["agent_context"].open_priorities_note is None
