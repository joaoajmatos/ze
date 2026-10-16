"""Frozen baseline for the commitment-intake calibration (phase 173, plan D-6).

Phase 173 deleted the two-surface conversation pipeline (163 speech-act request, 168 loop-gate
request) from product code. This module keeps a frozen copy of the 163 questions and fact rule, and
reuses `ze_worldstate.loop_judge` (still live for email, calendar and ingestion) so the same rows
can be replayed through the old pipeline. It lives under eval/ only and nothing imports it from
product code.

The baseline bars are the ones the old surfaces shipped with (163 calibrated 2026-10-09, 168
calibrated 2026-10-12). The old pipeline never saw what the turn created, so it books a loop on a
turn that already made a reminder or goal: those are the duplicate bookings 173 removes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from ze_agents.system_one import SystemOneQuestion, SystemOneResult
from ze_memory.extractor import PredicateFamily, admit_family
from ze_worldstate.loop_judge import (
    LoopGateSurfaceConfig,
    build_state as loop_build_state,
    decide as decide_loop,
    questions_for as loop_questions_for,
)

ASSISTANT_CAP = 1000

BASELINE_CHOICE_HOLD = 0.9
BASELINE_BIOGRAPHY_HOLD = 0.7
BASELINE_LOOP_BARS = LoopGateSurfaceConfig(
    enabled=True, loop_hold=0.75, explicit_hold=0.85, resolves_hold=0.8
)

_SPEECH_ACTS = (
    "fact",
    "forget",
    "reminder",
    "loop",
    "goal",
    "ingest",
    "drop",
    "clarify",
)

_SPEECH_ACT_CRITERIA: dict[str, str] = {
    "fact": (
        "The user states a durable fact about themselves that stays true: who they are, "
        "a standing preference, a relationship, a hard constraint, or a contact detail. "
        "No time attached. Examples: 'I prefer aisle seats', 'sou alérgico a amendoins', "
        "'my sister is called Ana'. "
        "Only a statement. A question is never a fact, even when it mentions one: "
        "'what is my sister called?', 'prefiro corredor ou janela?'."
    ),
    "forget": (
        "Only when the user retracts a standing fact they told you about themselves. "
        "Examples: 'forget that I like aisle seats', 'esquece que prefiro lugar no corredor'. "
        "Cancel, drop or abandon aimed at a reminder, loop or goal is NOT forget: "
        "'forget the dentist' cancelling a ping is reminder."
    ),
    "reminder": (
        "The user wants a ping at a specific time or date, or cancels one. "
        "Time wins over biography. "
        "Examples: 'remind me Tuesday at 3 to call the dentist', 'remember to call Mom at 3', "
        "'lembra-me terça às 3 de ligar ao dentista'. "
        "Cancelling a ping is reminder, not forget: 'forget the dentist', 'esquece o dentista'."
    ),
    "loop": (
        "The user voices a lingering concern or open question to keep an eye on, with no date, "
        "or drops one. Examples: 'I need to figure out whether to switch jobs', "
        "'preciso de decidir se mudo de emprego'. "
        "Dropping the concern is loop, not forget: 'forget the job switch', 'esquece a mudança de emprego'."
    ),
    "goal": (
        "The user states a multi-week outcome they want to achieve, or abandons one. "
        "Examples: 'I want to ship the thesis by June', 'quero acabar a tese até junho'. "
        "Abandoning the goal is goal, not forget: 'cancel the thesis goal', 'esquece a meta da tese'."
    ),
    "ingest": (
        "The user hands over material to read, import or store, such as a link, document or "
        "pasted text. Examples: 'read this article and remember it', "
        "'guarda este documento'."
    ),
    "drop": (
        "Filler, thanks, mood, weather, right-now location or anything not worth keeping. "
        "Also any question to the assistant, including one about what it knows of the user. "
        "Examples: 'thanks, that helps', 'estou cansado hoje', 'what is my sister called?'."
    ),
    "clarify": (
        "The message is too ambiguous to place. The user must be asked what they mean. "
        "Examples: 'remember that', 'lembra-te disso'."
    ),
}

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

QUESTIONS_163: dict[str, SystemOneQuestion] = {
    "speech_act": SystemOneQuestion(
        type="choice",
        instructions="Which speech act is the user's message?" + _USER_ONLY,
        criteria={a: _SPEECH_ACT_CRITERIA[a] for a in _SPEECH_ACTS},
    ),
    "family": SystemOneQuestion(
        type="choice",
        instructions="Which kind of durable self-fact does the user's message state?"
        + _USER_ONLY,
        criteria={
            **{f.value: _FAMILY_CRITERIA[f.value] for f in PredicateFamily},
            "drop": _FAMILY_CRITERIA["drop"],
        },
    ),
    "biography": SystemOneQuestion(
        type="noul",
        instructions=(
            "Does the user's message state a durable fact about themselves "
            "that would still be true in a month?" + _USER_ONLY
        ),
    ),
}


def shuffled_163(rng: random.Random) -> dict[str, SystemOneQuestion]:
    questions = dict(QUESTIONS_163)
    for qid in ("speech_act", "family"):
        base = QUESTIONS_163[qid]
        keys = list(base.criteria)
        rng.shuffle(keys)
        questions[qid] = replace(base, criteria={k: base.criteria[k] for k in keys})
    return questions


def state_163(prompt: str, response: str) -> dict[str, str]:
    return {"user": prompt, "assistant": response[:ASSISTANT_CAP]}


def state_168(prompt: str) -> dict[str, str]:
    return loop_build_state(prompt, "conversation")


def questions_168() -> dict[str, SystemOneQuestion]:
    return loop_questions_for("conversation")


def decide_fact_163(
    result: SystemOneResult,
    choice_hold: float = BASELINE_CHOICE_HOLD,
    biography_hold: float = BASELINE_BIOGRAPHY_HOLD,
) -> str:
    """`persist`, `hold` or `fallback` (rules 3-10 of the deleted 163 judge, bars as shipped)."""
    if result.outcome == "skip":
        return "fallback"
    act = result.answers.get("speech_act")
    family = result.answers.get("family")
    bio = result.answers.get("biography")
    if (
        act is None
        or act.type != "choice"
        or act.choice is None
        or act.confidence is None
        or family is None
        or family.type != "choice"
        or family.choice is None
        or family.confidence is None
        or bio is None
        or bio.type != "noul"
        or bio.noul is None
    ):
        return "fallback"
    if str(act.choice).strip().lower() != "fact":
        return "hold"
    if act.confidence < choice_hold:
        return "hold"
    if admit_family(family.choice) is None:
        return "hold"
    if family.confidence < choice_hold:
        return "hold"
    if bio.noul < biography_hold:
        return "hold"
    return "persist"


@dataclass(frozen=True)
class BaselineOutcome:
    fact: str
    loop: str

    @property
    def persists_fact(self) -> bool:
        return self.fact == "persist"

    @property
    def creates_loop(self) -> bool:
        return self.loop in ("create_declared", "create_suspected")


def decide_baseline(
    result_163: SystemOneResult, result_168: SystemOneResult
) -> BaselineOutcome:
    """Both old requests merged. Each ran independently, so a turn can persist and create."""
    return BaselineOutcome(
        fact=decide_fact_163(result_163),
        loop=decide_loop(result_168, BASELINE_LOOP_BARS, "conversation").kind,
    )
