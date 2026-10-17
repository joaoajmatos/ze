from __future__ import annotations

from ze_components.claims import ClaimPosture, claim_tone, headline_text
from ze_components.serialize import serialize_primitive


def _claim(**kw) -> ClaimPosture:
    base = dict(kind="fact", subject="loop", ref_id="l1")
    base.update(kw)
    return ClaimPosture(**base)


def test_claim_posture_serializes_nested_and_omits_none():
    from ze_components.organisms import ClaimCard

    card = ClaimCard(
        title="Ship it",
        claim=_claim(confidence=0.7, source="email", state="active"),
    )
    data = serialize_primitive(card)
    assert data["type"] == "claim_card"
    assert data["claim"] == {
        "kind": "fact",
        "subject": "loop",
        "ref_id": "l1",
        "confidence": 0.7,
        "source": "email",
        "state": "active",
        "slipped": False,
    }


def test_headline_text_uppercases_strips_and_truncates():
    assert headline_text("2 slipping · 1 at risk") == "2 SLIPPING · 1 AT RISK"
    assert headline_text("Ledger-Lite: launch!?") == "LEDGER-LITE: LAUNCH"
    assert headline_text("café ñ") == "CAFE N"
    assert len(headline_text("x" * 100)) == 40


def test_claim_tone_table():
    assert claim_tone(_claim(slipped=True)) == "hot"
    assert claim_tone(_claim(slipped=True), needs_user=True) == "hot"
    assert claim_tone(_claim(), needs_user=True) == "cream"
    assert claim_tone(_claim(kind="suspicion")) == "dotted"
    assert claim_tone(_claim(kind="inference")) == "dotted"
    assert claim_tone(_claim(kind=None, subject="workflow")) == "default"
    assert claim_tone(_claim(kind="priority")) == "default"


def test_headline_text_folds_portuguese_diacritics_instead_of_dropping_letters():
    assert headline_text("Ação à vista, São João") == "ACAO A VISTA SAO JOAO"
