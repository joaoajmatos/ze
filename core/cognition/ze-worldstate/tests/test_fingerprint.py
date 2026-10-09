from uuid import UUID

from ze_plugin.contribution import EvidenceRef

from ze_worldstate.fingerprint import compute_evidence_fingerprint


PINNED = "8c2fde7ec70d66212fc1ebccee916bac6a1275aae4da464096efafc696c36ebe"


def test_fingerprint_is_stable_across_evidence_ref_unification():
    # Pinned value: dismissed-loop fingerprints persisted before the EvidenceRef
    # unification must keep matching.
    refs = [
        EvidenceRef(kind="fact", id=UUID("11111111-1111-1111-1111-111111111111")),
        EvidenceRef(kind="episode", id=UUID("22222222-2222-2222-2222-222222222222")),
    ]
    assert compute_evidence_fingerprint(refs) == PINNED
    assert compute_evidence_fingerprint(refs[::-1]) == PINNED
