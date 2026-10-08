"""System One speech-act judge: questions, surface config and the admission decision.

Imports ze_agents types only — ze-memory never depends on ze-core.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from ze_agents.system_one import SystemOneQuestion
from ze_logging import get_logger

from ze_memory.extractor import PredicateFamily
from ze_memory.types import SpeechAct

log = get_logger(__name__)

ASSISTANT_CAP = 1000

_SPEECH_ACT_CRITERIA: dict[str, str] = {
    "fact": (
        "The user states a durable fact about themselves that stays true: who they are, "
        "a standing preference, a relationship, a hard constraint, or a contact detail. "
        "No time attached. Examples: 'I prefer aisle seats', 'sou alérgico a amendoins', "
        "'my sister is called Ana'."
    ),
    "forget": (
        "The user asks to erase something they said about themselves. "
        "Examples: 'forget that I like aisle seats', 'esquece que prefiro lugar no corredor'."
    ),
    "reminder": (
        "The user wants a ping at a specific time or date. Time wins over biography. "
        "Examples: 'remind me Tuesday at 3 to call the dentist', 'remember to call Mom at 3', "
        "'lembra-me terça às 3 de ligar ao dentista'."
    ),
    "loop": (
        "The user voices a lingering concern or open question to keep an eye on, with no date. "
        "Examples: 'I need to figure out whether to switch jobs', "
        "'preciso de decidir se mudo de emprego'."
    ),
    "goal": (
        "The user states a multi-week outcome they want to achieve. "
        "Examples: 'I want to ship the thesis by June', 'quero acabar a tese até junho'."
    ),
    "ingest": (
        "The user hands over material to read, import or store, such as a link, document or "
        "pasted text. Examples: 'read this article and remember it', "
        "'guarda este documento'."
    ),
    "drop": (
        "Filler, thanks, mood, weather, right-now location or anything not worth keeping. "
        "Examples: 'thanks, that helps', 'estou cansado hoje'."
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

_BIOGRAPHY_INSTRUCTIONS = (
    "Does the user's message state a durable fact about themselves "
    "that would still be true in a month?"
)

SPEECH_ACT_QUESTIONS: dict[str, SystemOneQuestion] = {
    "speech_act": SystemOneQuestion(
        type="choice",
        instructions="Which speech act is the user's message?",
        criteria={a.value: _SPEECH_ACT_CRITERIA[a.value] for a in SpeechAct},
    ),
    "family": SystemOneQuestion(
        type="choice",
        instructions="Which kind of durable self-fact does the user's message state?",
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
    config = settings if isinstance(settings, dict) else getattr(settings, "config", None)
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
