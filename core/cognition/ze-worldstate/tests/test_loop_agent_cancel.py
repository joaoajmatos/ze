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


class _ConfirmStore:
    def __init__(self, fail_confirm: bool = False) -> None:
        from ze_agents.claims import ClaimKind

        self.fail_confirm = fail_confirm
        self.bank = OpenLoop(
            id=uuid4(),
            title="Switch bank",
            claim_kind=ClaimKind.SUSPICION,
            provenance="email",
            confidence=0.35,
            state=LoopState.SUSPECTED,
        )
        self.dentist = OpenLoop(
            id=uuid4(),
            title="Dentist appointment",
            claim_kind=ClaimKind.SUSPICION,
            provenance="email",
            confidence=0.3,
            state=LoopState.SUSPECTED,
        )
        self.transitions: list[tuple] = []
        self.stamped: list = []

    async def list(self, states=None):
        return [self.bank, self.dentist]

    async def transition(self, loop_id, state, **kwargs):
        if self.fail_confirm and state == "active":
            raise RuntimeError("db down")
        self.transitions.append((loop_id, state))
        loop = self.bank if loop_id == self.bank.id else self.dentist
        return loop

    async def stamp_declared(self, loop_id, *, confidence, deadline):
        self.stamped.append(loop_id)

    async def list_evidence(self, loop_id):
        return []

    async def set_dismissed_evidence_fingerprint(self, loop_id, fingerprint):
        return None


def _confirm_agent(store: _ConfirmStore, reply: str) -> LoopsAgent:
    client = AsyncMock()
    client.complete_with_tools = AsyncMock(
        side_effect=[
            (None, [{"id": "c1", "name": "list_open_loops", "arguments": {}}]),
            (
                None,
                [
                    {
                        "id": "c2",
                        "name": "confirm_loop",
                        "arguments": {"loop_id": str(store.bank.id)},
                    },
                    {
                        "id": "c3",
                        "name": "drop_loop",
                        "arguments": {"loop_id": str(store.dentist.id)},
                    },
                ],
            ),
            (reply, None),
        ]
    )
    client.complete = AsyncMock(return_value=reply)
    return LoopsAgent(
        openrouter_client=client,
        loop_store=store,
        loop_tracker=_FakeTracker(TrackResult(ok=False, error="unused")),
    )


def test_loops_agent_declares_confirm_loop():
    assert "confirm_loop" in LoopsAgent.tools
    assert "confirm_loop" in _AGENT_INSTRUCTIONS


async def test_confirm_and_drop_by_id_keep_the_reply():
    store = _ConfirmStore()
    reply = "I'll keep track of the bank switch and dropped the dentist one."
    agent = _confirm_agent(store, reply)

    result = await agent.run(_ctx())

    assert (store.bank.id, "active") in store.transitions
    assert (store.dentist.id, "dropped") in store.transitions
    assert store.stamped == [store.bank.id]
    assert result.response == reply


async def test_failed_confirm_strips_the_tracking_claim():
    store = _ConfirmStore(fail_confirm=True)
    agent = _confirm_agent(store, "I'll keep track of the bank switch.")

    result = await agent.run(_ctx())

    assert result.response == COULD_NOT_TRACK
