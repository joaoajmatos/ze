"""System One admission gate: typed speech-act / family / biography judgments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ze_agents.system_one import SystemOneAnswer, SystemOneQuestion, SystemOneResult
from ze_memory.types import SpeechAct

ACT_ORDER: tuple[str, ...] = tuple(act.value for act in SpeechAct)
FAMILY_ORDER: tuple[str, ...] = (
    "identity",
    "preference",
    "relationship",
    "constraint",
    "contact_detail",
    "drop",
)

_ACT_CRITERIA = {
    "fact": "A durable statement about the user themselves with no time attached: who they are, what they prefer, who they know, a standing constraint, a contact detail. Ex: 'I prefer aisle seats', 'Sou alérgico a amendoim'.",
    "forget": "The user retracts a standing fact about themselves. Ex: 'forget that I like aisle seats', 'esquece que eu gosto de café'. Not for cancelling a reminder, loop, or goal.",
    "reminder": "The user wants to be pinged at or by a time, or cancels such a ping. Time wins over biography. Ex: 'remind me Tuesday', 'remember to call Mom at 3', 'forget the dentist' meaning cancel the ping, 'lembra-me amanhã às 9'.",
    "loop": "A lingering concern or open question with no fixed time that the user keeps carrying. Ex: 'I need to figure out whether to switch jobs'.",
    "goal": "A multi-week outcome the user wants to achieve. Ex: 'I want to ship the thesis by June'.",
    "ingest": "The user asks to import, read, or save a document, file, or link.",
    "drop": "Filler, thanks, mood, weather, right-now location, small talk, or anything not worth storing.",
    "clarify": "The user's meaning is genuinely ambiguous between the other labels.",
}

_FAMILY_CRITERIA = {
    "identity": "Name, age, job, residence, background of the user.",
    "preference": "A standing like, dislike, or habit of the user.",
    "relationship": "A durable relationship between the user and a person.",
    "constraint": "A standing rule or limit: allergy, never/always, availability.",
    "contact_detail": "A phone, email, or address belonging to the user or someone they know.",
    "drop": "None of the above: ephemeral, timed, mood, commitment, schedule.",
}

_ACT_INSTRUCTIONS = (
    "Which single speech act is the USER's message? Judge the user's words; the "
    "assistant reply is context only."
)
_FAMILY_INSTRUCTIONS = (
    "If the user's message states a durable fact about themselves, which family is it? "
    "Choose drop when it is not a durable self-fact."
)
_BIOGRAPHY_INSTRUCTIONS = (
    "Does the user's message state a durable fact about themselves that should be "
    "remembered long-term, with no time or reminder attached?"
)

_ASSISTANT_CAP = 1000


@dataclass(frozen=True)
class AdmissionThresholds:
    """Hold bars. Uncalibrated until measured on Ze fixtures (spec 163 FR-010)."""

    act_min_peakedness: float
    family_min_peakedness: float
    biography_min: float


@dataclass
class AdmissionDecision:
    outcome: str  # "admit" | "hold" | "skip"
    family: str | None = None
    judgments: list[dict[str, Any]] | None = None


def _system_one_config(settings: Any) -> dict:
    if settings is None:
        return {}
    raw = settings if isinstance(settings, dict) else getattr(settings, "config", None)
    if not isinstance(raw, dict):
        return {}
    return raw.get("system_one") or {}


def thresholds_from_settings(settings: Any) -> AdmissionThresholds | None:
    """Return thresholds only when the surface is on and every bar is configured."""
    cfg = _system_one_config(settings)
    if not cfg.get("enabled", False):
        return None
    surface = (cfg.get("surfaces") or {}).get("speech_act") or {}
    if not surface.get("enabled", False):
        return None
    try:
        return AdmissionThresholds(
            act_min_peakedness=float(surface["act_min_peakedness"]),
            family_min_peakedness=float(surface["family_min_peakedness"]),
            biography_min=float(surface["biography_min"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def build_questions() -> dict[str, SystemOneQuestion]:
    return {
        "speech_act": SystemOneQuestion(
            type="choice",
            instructions=_ACT_INSTRUCTIONS,
            criteria={k: _ACT_CRITERIA[k] for k in ACT_ORDER},
        ),
        "family": SystemOneQuestion(
            type="choice",
            instructions=_FAMILY_INSTRUCTIONS,
            criteria={k: _FAMILY_CRITERIA[k] for k in FAMILY_ORDER},
        ),
        "biography": SystemOneQuestion(
            type="noul", instructions=_BIOGRAPHY_INSTRUCTIONS
        ),
    }


def _judgment_row(
    qid: str, answer: SystemOneAnswer, result: SystemOneResult
) -> dict[str, Any]:
    value: str | float | None = (
        answer.choice if answer.type == "choice" else answer.noul
    )
    return {
        "question_id": qid,
        "kind": answer.type,
        "latency_ms": result.latency_ms,
        "answer": value,
        "probabilities": answer.probabilities,
        "peakedness": answer.confidence,
        "model": result.model,
        "input_tokens": result.input_tokens,
        "consumed": False,
        "skip_reason": None,
    }


def decide(
    result: SystemOneResult,
    thresholds: AdmissionThresholds,
    *,
    admit_speech_act,
    admit_family,
) -> AdmissionDecision:
    if result.outcome != "ok":
        return AdmissionDecision(
            outcome="skip",
            judgments=[
                {
                    "question_id": "speech_act",
                    "kind": "choice",
                    "latency_ms": result.latency_ms,
                    "answer": None,
                    "probabilities": None,
                    "peakedness": None,
                    "model": result.model,
                    "input_tokens": None,
                    "consumed": False,
                    "skip_reason": result.skip_reason,
                }
            ],
        )

    rows = {
        qid: _judgment_row(qid, answer, result)
        for qid, answer in result.answers.items()
        if qid in ("speech_act", "family", "biography")
    }
    judgments = list(rows.values())

    act_answer = result.answers.get("speech_act")
    if act_answer is None:
        return AdmissionDecision(outcome="hold", judgments=judgments)
    rows["speech_act"]["consumed"] = True

    if admit_speech_act(act_answer.choice) is not SpeechAct.FACT:
        return AdmissionDecision(outcome="hold", judgments=judgments)
    if (
        act_answer.confidence is None
        or act_answer.confidence < thresholds.act_min_peakedness
    ):
        return AdmissionDecision(outcome="hold", judgments=judgments)

    family_answer = result.answers.get("family")
    bio_answer = result.answers.get("biography")
    if family_answer is None or bio_answer is None:
        return AdmissionDecision(outcome="hold", judgments=judgments)
    rows["family"]["consumed"] = True
    rows["biography"]["consumed"] = True

    family = admit_family(family_answer.choice)
    if family is None:
        return AdmissionDecision(outcome="hold", judgments=judgments)
    if (
        family_answer.confidence is None
        or family_answer.confidence < thresholds.family_min_peakedness
    ):
        return AdmissionDecision(outcome="hold", judgments=judgments)
    if bio_answer.noul is None or bio_answer.noul < thresholds.biography_min:
        return AdmissionDecision(outcome="hold", judgments=judgments)
    return AdmissionDecision(outcome="admit", family=family, judgments=judgments)


async def judge_admission(
    client: Any,
    *,
    prompt: str,
    response: str,
    thresholds: AdmissionThresholds,
    admit_speech_act,
    admit_family,
) -> AdmissionDecision:
    result = await client.evaluate(
        {"user": prompt, "assistant": response[:_ASSISTANT_CAP]},
        build_questions(),
    )
    return decide(
        result,
        thresholds,
        admit_speech_act=admit_speech_act,
        admit_family=admit_family,
    )
