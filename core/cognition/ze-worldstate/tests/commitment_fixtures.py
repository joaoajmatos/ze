"""Shared builders for commitment-intake tests."""

from __future__ import annotations

from ze_agents.nested_tools import TurnCreation
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_memory.types import CommitmentChoice

from ze_worldstate.commitment_judge import (
    COMMITMENT_QUESTIONS,
    CommitmentIntakeSurfaceConfig,
)

_BARS = dict(
    choice_hold=0.6,
    family_hold=0.6,
    biography_hold=0.7,
    loop_hold=0.5,
    explicit_hold=0.8,
    resolves_hold=0.85,
)
_CAL = CommitmentIntakeSurfaceConfig(enabled=True, **_BARS)
_NONE = TurnCreation()
_LABELS = [c.value for c in CommitmentChoice]
_FAMILIES = list(COMMITMENT_QUESTIONS["family"].criteria)


def _choice(label, options, confidence):
    return SystemOneAnswer(
        type="choice",
        choice=label,
        confidence=confidence,
        probabilities={o: (confidence if o == label else 0.0) for o in options},
    )


def make(
    choice="loop",
    *,
    conf=0.95,
    family="preference",
    family_conf=0.95,
    bio=0.95,
    concern=0.9,
    explicit=0.9,
    resolves=0.1,
) -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        model="jev-test",
        input_tokens=10,
        latency_ms=5,
        answers={
            "commitment": _choice(choice, _LABELS, conf),
            "family": _choice(family, _FAMILIES, family_conf),
            "biography": SystemOneAnswer(type="noul", noul=bio),
            "is_open_concern": SystemOneAnswer(type="noul", noul=concern),
            "explicit_declaration": SystemOneAnswer(type="noul", noul=explicit),
            "resolves_existing": SystemOneAnswer(type="noul", noul=resolves),
        },
    )


async def conversation_admit(inflow, configurable: dict, *, prompt: str):
    """The pre-173 conversation gate (loop_gate surface), kept for tests of the commit paths."""
    from ze_worldstate.loop_judge import CONVERSATION
    from ze_worldstate.types import SourceKey

    thread_id = configurable.get("thread_id")
    admission = await inflow._judge(prompt, CONVERSATION)
    admission.source = SourceKey(CONVERSATION, str(thread_id)) if thread_id else None
    return admission
