"""System One speech-act judge: questions, surface config and the admission decision.

Imports ze_agents types only — ze-memory never depends on ze-core.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from ze_agents.system_one import SystemOneAnswer, SystemOneQuestion, SystemOneResult
from ze_logging import get_logger

from ze_memory.extractor import PredicateFamily, admit_family, admit_speech_act
from ze_memory.types import SpeechAct

log = get_logger(__name__)

ASSISTANT_CAP = 1000

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

_BIOGRAPHY_INSTRUCTIONS = (
    "Does the user's message state a durable fact about themselves "
    "that would still be true in a month?" + _USER_ONLY
)

SPEECH_ACT_QUESTIONS: dict[str, SystemOneQuestion] = {
    "speech_act": SystemOneQuestion(
        type="choice",
        instructions="Which speech act is the user's message?" + _USER_ONLY,
        criteria={a.value: _SPEECH_ACT_CRITERIA[a.value] for a in SpeechAct},
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
    "biography": SystemOneQuestion(type="noul", instructions=_BIOGRAPHY_INSTRUCTIONS),
}


def build_state(prompt: str, response: str) -> dict[str, str]:
    return {"user": prompt, "assistant": response[:ASSISTANT_CAP]}


@dataclass(frozen=True)
class SpeechActSurfaceConfig:
    enabled: bool = False
    choice_hold: float | None = None
    biography_hold: float | None = None

    @property
    def calibrated(self) -> bool:
        return (
            self.enabled
            and self.choice_hold is not None
            and self.biography_hold is not None
        )


def _bar(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        log.warning("speech_act_bar_invalid", bar=name)
        return None
    if math.isnan(value) or not 0.0 <= value <= 1.0:
        log.warning("speech_act_bar_invalid", bar=name)
        return None
    return float(value)


def speech_act_surface_config(settings: Any) -> SpeechActSurfaceConfig:
    config = (
        settings if isinstance(settings, dict) else getattr(settings, "config", None)
    )
    if not isinstance(config, dict):
        return SpeechActSurfaceConfig()
    system_one = config.get("system_one")
    surfaces = system_one.get("surfaces") if isinstance(system_one, dict) else None
    block = surfaces.get("speech_act") if isinstance(surfaces, dict) else None
    if not isinstance(block, dict):
        return SpeechActSurfaceConfig()
    return SpeechActSurfaceConfig(
        enabled=block.get("enabled") is True,
        choice_hold=_bar(block.get("choice_hold"), "choice_hold"),
        biography_hold=_bar(block.get("biography_hold"), "biography_hold"),
    )


AdmissionKind = Literal["persist", "hold", "skip"]


@dataclass(frozen=True)
class AdmissionDecision:
    kind: AdmissionKind
    reason: str
    family: str | None = None
    consumed: frozenset[str] = frozenset()


_ALL_QUESTIONS = frozenset(SPEECH_ACT_QUESTIONS)
_ACT_AND_FAMILY = frozenset({"speech_act", "family"})


def _valid_choice(answer: SystemOneAnswer | None) -> bool:
    return (
        answer is not None
        and answer.type == "choice"
        and answer.choice is not None
        and answer.confidence is not None
    )


def _valid_noul(answer: SystemOneAnswer | None) -> bool:
    return answer is not None and answer.type == "noul" and answer.noul is not None


def decide(result: SystemOneResult, cfg: SpeechActSurfaceConfig) -> AdmissionDecision:
    """Pure admission decision over one System One result (research R7, rules 3-10).

    Rules 1 and 2 (trivial turn, surface off or bar unset) never reach a result.
    """
    if result.outcome == "skip":
        return AdmissionDecision("skip", result.skip_reason or "error")

    act = result.answers.get("speech_act")
    family = result.answers.get("family")
    bio = result.answers.get("biography")
    if not (_valid_choice(act) and _valid_choice(family) and _valid_noul(bio)):
        return AdmissionDecision("skip", "invalid_answer")
    if cfg.choice_hold is None or cfg.biography_hold is None:
        return AdmissionDecision("skip", "uncalibrated")

    if admit_speech_act(act.choice) is not SpeechAct.FACT:
        return AdmissionDecision("hold", "not_fact", consumed=frozenset({"speech_act"}))
    if act.confidence < cfg.choice_hold:
        return AdmissionDecision(
            "hold", "act_unsure", consumed=frozenset({"speech_act"})
        )
    kept = admit_family(family.choice)
    if kept is None:
        return AdmissionDecision("hold", "family_drop", consumed=_ACT_AND_FAMILY)
    if family.confidence < cfg.choice_hold:
        return AdmissionDecision("hold", "family_unsure", consumed=_ACT_AND_FAMILY)
    if bio.noul < cfg.biography_hold:
        return AdmissionDecision("hold", "not_biography", consumed=_ALL_QUESTIONS)
    return AdmissionDecision("persist", "persist", family=kept, consumed=_ALL_QUESTIONS)
