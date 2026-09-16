from dataclasses import dataclass

from ze_agents.claims import ClaimKind, Provenance
from ze_agents.types import AgentResult, ClaimBearingProposal


@dataclass
class _FakeProposal:
    claim_kind: ClaimKind
    provenance: Provenance
    confidence: float


def test_shape_matching_object_satisfies_protocol():
    proposal = _FakeProposal(
        claim_kind=ClaimKind.IDENTITY,
        provenance=Provenance.SYNTHESIZED,
        confidence=0.9,
    )
    assert isinstance(proposal, ClaimBearingProposal)


def test_object_missing_fields_does_not_satisfy_protocol():
    class _Bare:
        pass

    assert not isinstance(_Bare(), ClaimBearingProposal)


def test_agent_result_proposal_fields_default_to_empty_list():
    result = AgentResult(agent="companion", response="hi")
    assert result.contact_proposals == []
