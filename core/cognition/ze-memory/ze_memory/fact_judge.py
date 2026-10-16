"""System One fact judge: the family and biography questions and the fact persist/hold rules.

The commitment Choice, surface config and merged decision live in ze-worldstate (173).

Imports ze_agents types only — ze-memory never depends on ze-core.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ze_agents.system_one import (
    SystemOneAnswer,
    SystemOneQuestion,
    valid_choice,
    valid_noul,
)

from ze_memory.extractor import PredicateFamily, admit_family

ASSISTANT_CAP = 1000

_FAMILY_CRITERIA: dict[str, str] = {
    "identity": "Who the user is: name, age, job, home city, language. 'I am a nurse', 'sou de Lisboa'.",
    "preference": "A standing like, dislike or habit. 'I prefer aisle seats', 'prefiro lugar no corredor'.",
    "relationship": "A durable tie to a person. 'my sister is Ana', 'a minha mulher chama-se Rita'.",
    "constraint": "A hard limit: allergy, diet, rule. 'allergic to peanuts', 'não como carne'.",
    "contact_detail": "A phone number, address or handle that belongs to the user. 'my number is …'.",
    "drop": (
        "Not a durable self-fact: mood, weather, schedule, commitments, right-now location. "
        "'I am tired today', 'tenho dentista terça'."
    ),
}

_USER_ONLY = " Judge the user's words; the assistant reply is context only."

_BIOGRAPHY_INSTRUCTIONS = (
    "Does the user's message state a durable fact about themselves "
    "that would still be true in a month?" + _USER_ONLY
)

FACT_QUESTIONS: dict[str, SystemOneQuestion] = {
    "family": SystemOneQuestion(
        type="choice",
        instructions="Which kind of durable self-fact does the user's message state?"
        + _USER_ONLY,
        criteria={
            **{f.value: _FAMILY_CRITERIA[f.value] for f in PredicateFamily},
            "drop": _FAMILY_CRITERIA["drop"],
        },
    ),
    "biography": SystemOneQuestion(type="noul", instructions=_BIOGRAPHY_INSTRUCTIONS),
}


def build_state(prompt: str, response: str) -> dict[str, str]:
    return {"user": prompt, "assistant": response[:ASSISTANT_CAP]}


@dataclass(frozen=True)
class FactBars:
    family_hold: float
    biography_hold: float


AdmissionKind = Literal["persist", "hold", "skip"]


@dataclass(frozen=True)
class AdmissionDecision:
    kind: AdmissionKind
    reason: str
    family: str | None = None
    consumed: frozenset[str] = frozenset()


_FAMILY = frozenset({"family"})
_BOTH = frozenset({"family", "biography"})


def decide_fact(
    family: SystemOneAnswer | None,
    biography: SystemOneAnswer | None,
    bars: FactBars,
) -> AdmissionDecision:
    """Pure fact decision once the commitment Choice has said `fact` (163 rules 7-9)."""
    if not (valid_choice(family) and valid_noul(biography, unit_range=False)):
        return AdmissionDecision("skip", "invalid_answer")
    kept = admit_family(family.choice)
    if kept is None:
        return AdmissionDecision("hold", "family_drop", consumed=_FAMILY)
    if family.confidence < bars.family_hold:
        return AdmissionDecision("hold", "family_unsure", consumed=_FAMILY)
    if biography.noul < bars.biography_hold:
        return AdmissionDecision("hold", "not_biography", consumed=_BOTH)
    return AdmissionDecision("persist", "persist", family=kept, consumed=_BOTH)
