from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.label_match import Ambiguous, Miss, Unique, precise_label_match
from ze_agents.nested_tools import COULD_NOT_TRACK
from ze_agents.types import AgentContext
from ze_worldstate.agents.agent import LoopsAgent, _AGENT_INSTRUCTIONS
from ze_worldstate.types import (
    LoopProvenance,
    LoopState,
    OpenLoop,
    TrackOutcome,
    TrackResult,
)


def test_loops_agent_catalog():
    assert LoopsAgent.name == "loops"
    assert "list_open_loops" in LoopsAgent.tools
    assert "track_loop" in LoopsAgent.tools
    assert "close_loop" in LoopsAgent.tools
    assert "drop_loop" in LoopsAgent.tools
    assert "forget_fact" not in LoopsAgent.tools


def test_instructions_require_unique_title_match():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "list_open_loops" in text
    assert "unique" in text
    assert "at most once" in text
    assert "never batch" in text


def test_instructions_cover_tracking():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "track_loop" in text
    assert "only after" in text


class _FakeTracker:
    def __init__(self, result: TrackResult) -> None:
        self.result = result

    async def track(self, title: str, window_days: int = 0) -> TrackResult:
        return self.result


def _tracked_loop() -> OpenLoop:
    from ze_agents.claims import ClaimKind

    return OpenLoop(
        id=uuid4(),
        title="Porto move",
        claim_kind=ClaimKind.PRIORITY,
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.9,
        state=LoopState.ACTIVE,
    )


def _agent(result: TrackResult, reply: str) -> tuple[LoopsAgent, str]:
    client = AsyncMock()
    client.complete_with_tools = AsyncMock(
        side_effect=[
            (
                None,
                [
                    {
                        "id": "c1",
                        "name": "track_loop",
                        "arguments": {"title": "Porto move"},
                    }
                ],
            ),
            (reply, None),
        ]
    )
    client.complete = AsyncMock(return_value=reply)
    agent = LoopsAgent(
        openrouter_client=client,
        loop_store=AsyncMock(),
        loop_tracker=_FakeTracker(result),
    )
    return agent, reply


def _ctx() -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt="keep the Porto move on my radar",
        intent="manage",
    )


async def test_successful_track_loop_keeps_the_reply():
    reply = "I'll keep that on my radar."
    agent, _ = _agent(
        TrackResult(ok=True, outcome=TrackOutcome.CREATED, loop=_tracked_loop()), reply
    )

    result = await agent.run(_ctx())

    assert result.response == reply


async def test_failed_track_loop_strips_the_claim():
    reply = "I'll keep that on my radar."
    agent, _ = _agent(TrackResult(ok=False, error="db down"), reply)

    result = await agent.run(_ctx())

    assert result.response == COULD_NOT_TRACK


def test_two_job_titles_are_ambiguous_or_miss():
    result = precise_label_match(
        "forget the job",
        [(uuid4(), "Job switch worry"), (uuid4(), "Job interview loop")],
    )
    assert isinstance(result, (Ambiguous, Miss))


def test_unique_loop_title_matches():
    loop_id = uuid4()
    result = precise_label_match(
        "forget the job switch worry",
        [(loop_id, "Job switch worry"), (uuid4(), "Call mom")],
    )
    assert isinstance(result, Unique)
    assert result.item_id == loop_id


def test_forget_that_is_miss_not_a_write():
    result = precise_label_match(
        "forget that",
        [(uuid4(), "Job switch worry")],
    )
    assert isinstance(result, Miss)
