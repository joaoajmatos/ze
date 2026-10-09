"""Gold System One answers (EN + PT) for the speech-act admission judge."""

from __future__ import annotations

from dataclasses import dataclass

from ze_agents.system_one import SystemOneAnswer, SystemOneResult

from ze_memory.speech_act_judge import SPEECH_ACT_QUESTIONS

ACT_IDS = tuple(SPEECH_ACT_QUESTIONS["speech_act"].criteria)
FAMILY_IDS = tuple(SPEECH_ACT_QUESTIONS["family"].criteria)


def choice_answer(label: str, options, confidence: float = 0.95) -> SystemOneAnswer:
    others = [o for o in options if o != label]
    rest = (1.0 - confidence) / len(others) if others else 0.0
    probabilities = {o: (confidence if o == label else rest) for o in options}
    return SystemOneAnswer(
        type="choice", choice=label, confidence=confidence, probabilities=probabilities
    )


def make_result(
    act: str,
    family: str,
    *,
    act_confidence: float = 0.95,
    family_confidence: float = 0.95,
    noul: float = 0.95,
) -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        model="typesafe/jev-1.13-test",
        input_tokens=100,
        latency_ms=40,
        answers={
            "speech_act": choice_answer(act, ACT_IDS, act_confidence),
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
    act: str
    family: str
    persist: bool
    noul: float

    def result(self, **overrides) -> SystemOneResult:
        params = {"noul": self.noul, **overrides}
        return make_result(self.act, self.family, **params)


def _turn(id, lang, user, assistant, act, family, persist=False):
    return GoldTurn(
        id, lang, user, assistant, act, family, persist, 0.95 if persist else 0.05
    )


REMINDER = [
    _turn(
        "timed-en",
        "en",
        "Remind me Tuesday at 3 to call the dentist.",
        "Done, Tuesday at 3.",
        "reminder",
        "drop",
    ),
    _turn(
        "timed-pt",
        "pt",
        "Lembra-me terça às 3 de ligar ao dentista.",
        "Feito, terça às 3.",
        "reminder",
        "drop",
    ),
    _turn(
        "remember-to-en",
        "en",
        "Remember to call Mom at 3.",
        "I'll ping you at 3.",
        "reminder",
        "drop",
    ),
    _turn(
        "remember-to-pt",
        "pt",
        "Lembra-te de ligar à mãe às 3.",
        "Aviso-te às 3.",
        "reminder",
        "drop",
    ),
]
LOOP = [
    _turn(
        "loop-en",
        "en",
        "I need to figure out whether to switch jobs.",
        "Want to talk it through?",
        "loop",
        "drop",
    ),
    _turn(
        "loop-pt",
        "pt",
        "Preciso de decidir se mudo de emprego.",
        "Queres falar sobre isso?",
        "loop",
        "drop",
    ),
]
GOAL = [
    _turn(
        "goal-en",
        "en",
        "Help me ship the thesis by June.",
        "Let's plan it.",
        "goal",
        "drop",
    ),
    _turn(
        "goal-pt",
        "pt",
        "Ajuda-me a acabar a tese até junho.",
        "Vamos planear.",
        "goal",
        "drop",
    ),
]
INGEST = [
    _turn(
        "ingest-en",
        "en",
        "Read this article and keep it: https://example.com/a",
        "Saved it.",
        "ingest",
        "drop",
    ),
    _turn(
        "ingest-pt",
        "pt",
        "Guarda este artigo: https://example.com/a",
        "Guardado.",
        "ingest",
        "drop",
    ),
]
DROP = [
    _turn(
        "mood-en", "en", "I'm tired today and it's raining.", "Rest up.", "drop", "drop"
    ),
    _turn("commit-en", "en", "I'll call Mom Tuesday.", "Sounds good.", "drop", "drop"),
    _turn(
        "mood-pt",
        "pt",
        "Estou cansado hoje e está a chover.",
        "Descansa.",
        "drop",
        "drop",
    ),
]
PERSIST = [
    _turn(
        "aisle-pref-en",
        "en",
        "I prefer aisle seats.",
        "Noted.",
        "fact",
        "preference",
        True,
    ),
    _turn(
        "aisle-pref-pt",
        "pt",
        "Prefiro lugar no corredor.",
        "Anotado.",
        "fact",
        "preference",
        True,
    ),
    _turn(
        "peanut-en",
        "en",
        "I'm allergic to peanuts.",
        "Good to know.",
        "fact",
        "constraint",
        True,
    ),
    _turn(
        "peanut-pt",
        "pt",
        "Sou alérgico a amendoins.",
        "Bom saber.",
        "fact",
        "constraint",
        True,
    ),
]
DENTIST_CANCEL = [
    _turn(
        "dentist-cancel-en",
        "en",
        "Forget the dentist.",
        "Cancelled the dentist reminder.",
        "reminder",
        "drop",
    ),
    _turn(
        "dentist-cancel-pt",
        "pt",
        "Esquece o dentista.",
        "Cancelei o lembrete do dentista.",
        "reminder",
        "drop",
    ),
]
AISLE_RETRACT = [
    _turn(
        "aisle-forget-en",
        "en",
        "Forget that I like aisle seats.",
        "Okay, forgotten.",
        "forget",
        "drop",
    ),
    _turn(
        "aisle-forget-pt",
        "pt",
        "Esquece que prefiro lugar no corredor.",
        "Esquecido.",
        "forget",
        "drop",
    ),
]
NON_FACT = REMINDER + LOOP + GOAL + INGEST + DROP + DENTIST_CANCEL + AISLE_RETRACT


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
