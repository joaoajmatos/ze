import pytest
from ze_agents.claims import ClaimKind
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop, loop_claim_kind

EXPECTED = {
    LoopState.SUSPECTED: ClaimKind.SUSPICION,
    LoopState.ACTIVE: ClaimKind.PRIORITY,
    LoopState.DRIFTING: ClaimKind.PRIORITY,
    LoopState.CLOSED: ClaimKind.PRIORITY,
    LoopState.DROPPED: None,
}


@pytest.mark.parametrize("state", list(LoopState))
def test_loop_claim_kind_covers_every_state(state):
    assert loop_claim_kind(state) is EXPECTED[state]


@pytest.mark.parametrize("state", list(LoopState))
def test_open_loop_claim_kind_follows_its_state(state):
    loop = OpenLoop(
        title="Renew passport",
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.5,
        state=state,
    )
    assert loop.claim_kind is EXPECTED[state]


def test_open_loop_claim_kind_changes_when_state_changes():
    loop = OpenLoop(title="x", provenance=LoopProvenance.CONVERSATION, confidence=0.5)
    assert loop.claim_kind is ClaimKind.SUSPICION
    loop.state = LoopState.ACTIVE
    assert loop.claim_kind is ClaimKind.PRIORITY


def test_open_loop_rejects_a_claim_kind_argument():
    with pytest.raises(TypeError):
        OpenLoop(  # type: ignore[call-arg]
            title="x",
            provenance=LoopProvenance.CONVERSATION,
            confidence=0.5,
            claim_kind=ClaimKind.PRIORITY,
        )
