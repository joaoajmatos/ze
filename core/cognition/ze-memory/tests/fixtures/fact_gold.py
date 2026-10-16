"""Gold System One fact answers (EN + PT) for the fact judge (family + biography)."""

from __future__ import annotations

from dataclasses import dataclass

from ze_agents.system_one import SystemOneAnswer, SystemOneResult

from ze_memory.fact_judge import FACT_QUESTIONS

FAMILY_IDS = tuple(FACT_QUESTIONS["family"].criteria)


def choice_answer(label: str, options, confidence: float = 0.95) -> SystemOneAnswer:
    others = [o for o in options if o != label]
    rest = (1.0 - confidence) / len(others) if others else 0.0
    probabilities = {o: (confidence if o == label else rest) for o in options}
    return SystemOneAnswer(
        type="choice", choice=label, confidence=confidence, probabilities=probabilities
    )


def make_result(
    family: str,
    *,
    family_confidence: float = 0.95,
    noul: float = 0.95,
) -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        model="typesafe/jev-1.13-test",
        input_tokens=100,
        latency_ms=40,
        answers={
            "family": choice_answer(family, FAMILY_IDS, family_confidence),
            "biography": SystemOneAnswer(type="noul", noul=noul),
        },
    )


@dataclass(frozen=True)
class GoldTurn:
    id: str
    lang: str
    user: str
    assistant: str
    family: str
    persist: bool
    noul: float

    def result(self, **overrides) -> SystemOneResult:
        params = {"noul": self.noul, **overrides}
        return make_result(self.family, **params)


def _turn(id, lang, user, assistant, family, persist=False):
    return GoldTurn(
        id, lang, user, assistant, family, persist, 0.95 if persist else 0.05
    )


PERSIST = [
    _turn(
        "aisle-pref-en",
        "en",
        "I prefer aisle seats.",
        "Noted.",
        "preference",
        True,
    ),
    _turn(
        "aisle-pref-pt",
        "pt",
        "Prefiro lugar no corredor.",
        "Anotado.",
        "preference",
        True,
    ),
    _turn(
        "peanut-en",
        "en",
        "I'm allergic to peanuts.",
        "Good to know.",
        "constraint",
        True,
    ),
    _turn(
        "peanut-pt",
        "pt",
        "Sou alérgico a amendoins.",
        "Bom saber.",
        "constraint",
        True,
    ),
]


class FakeSystemOneClient:
    """Satisfies SystemOneClient; returns a fixed result and records each call."""

    def __init__(self, result: SystemOneResult) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def evaluate(self, state, questions, *, max_attempts=None):
        self.calls.append(
            {"state": state, "questions": questions, "max_attempts": max_attempts}
        )
        return self.result
