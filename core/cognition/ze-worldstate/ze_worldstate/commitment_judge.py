"""Commitment-intake judgment — one System One request per conversation turn.

The `commitment` Choice, the fact questions (ze-memory) and the loop Nouls (168) are asked in one
batch; pure `decide()` merges them with what the turn already created
(specs/phases/173-commitment-intake/contracts/commitment-judgment.md).
Imports ze_agents types only; ze-worldstate never depends on ze-core.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from ze_agents.nested_tools import TurnCreation
from ze_agents.system_one import SystemOneAnswer, SystemOneQuestion, SystemOneResult
from ze_logging import get_logger
from ze_memory.fact_judge import (
    FACT_QUESTIONS,
    FactBars,
    build_state as build_state,
    decide_fact,
)
from ze_memory.types import CommitmentChoice

from ze_worldstate.loop_judge import LOOP_QUESTIONS, Q_CONCERN, Q_RESOLVES

log = get_logger(__name__)

Q_COMMITMENT = "commitment"
Q_EXPLICIT = "explicit_declaration"

_EXPLICIT_INSTRUCTIONS = (
    "Does the user say, in the first person, that they need to, have to or must do "
    "something, or ask to be reminded of it?"
)

_USER_ONLY = " Judge the user's words; the assistant reply is context only."

_COMMITMENT_CRITERIA: dict[str, str] = {
    "reminder": (
        "The user asks for a ping, alarm or nudge at a specific time or date, or cancels one. "
        "The ask is what makes it a reminder. "
        "Examples: 'remind me Tuesday at 3 to call the dentist', 'ping me at 6 to take the bins "
        "out', 'lembra-me terça às 3 de ligar ao dentista', 'avisa-me às 6 para sair'. "
        "A first-person obligation with a deadline and no ask to be pinged is a loop, not this: "
        "'I have to send the tax form by Friday'. "
        "Cancelling a ping stays here: 'forget the dentist', 'esquece o dentista'."
    ),
    "loop": (
        "The user voices a lingering concern, open question or obligation to keep an eye on, "
        "with or without a deadline but with no ask to be pinged at a time, or drops one. "
        "Examples: 'I need to figure out whether to switch jobs', "
        "'I haven't decided on the job offer yet', 'I have to send the tax form by Friday', "
        "'preciso de decidir se mudo de emprego', 'tenho de entregar o IRS até sexta', "
        "'preciso de renovar o passaporte antes da viagem'. "
        "Dropping the concern stays here: 'forget the job switch', 'esquece a mudança de emprego'."
    ),
    "goal": (
        "The user states a multi-week outcome they want to pursue and build up over time, or "
        "abandons one. A one-off task with a deadline is not a goal. "
        "Examples: 'I want to ship the thesis by June', 'I want to learn Portuguese up to B1 "
        "in three months', 'quero acabar a tese até junho', 'quero correr uma meia maratona "
        "este ano'. "
        "Abandoning the outcome stays here: 'cancel the thesis goal', 'esquece a meta da tese'."
    ),
    "waiting_on": (
        "The user is waiting for another person or party to act or answer. "
        "Examples: 'my landlord said he'd get back to me about the deposit', "
        "'ainda espero resposta do banco', 'the recruiter owes me a reply'."
    ),
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
        "Cancelling a ping, dropping a concern or abandoning an outcome is not this."
    ),
    "ingest": (
        "The user hands over material to read, import or store, such as a link, document or "
        "pasted text. Examples: 'read this article and remember it', "
        "'guarda este documento'."
    ),
    "clarify": (
        "The message is too ambiguous to place. The user must be asked what they mean. "
        "Examples: 'remember that', 'lembra-te disso'."
    ),
    "none": (
        "Filler, thanks, mood, weather, right-now location, an idle plan with no commitment, or "
        "anything not worth keeping. Also any question to the assistant, including one about what "
        "it knows of the user. "
        "Examples: 'thanks, that helps', 'estou cansado hoje', 'what is my sister called?'."
    ),
}

COMMITMENT_QUESTIONS: dict[str, SystemOneQuestion] = {
    Q_COMMITMENT: SystemOneQuestion(
        type="choice",
        instructions="Which kind of commitment is the user's message?" + _USER_ONLY,
        criteria={c.value: _COMMITMENT_CRITERIA[c.value] for c in CommitmentChoice},
    ),
    **FACT_QUESTIONS,
    **LOOP_QUESTIONS,
    Q_EXPLICIT: SystemOneQuestion(type="noul", instructions=_EXPLICIT_INSTRUCTIONS),
}

_BAR_NAMES = (
    "choice_hold",
    "family_hold",
    "biography_hold",
    "loop_hold",
    "explicit_hold",
    "resolves_hold",
)


@dataclass(frozen=True)
class CommitmentIntakeSurfaceConfig:
    enabled: bool = False
    choice_hold: float | None = None
    family_hold: float | None = None
    biography_hold: float | None = None
    loop_hold: float | None = None
    explicit_hold: float | None = None
    resolves_hold: float | None = None

    @property
    def calibrated(self) -> bool:
        return self.enabled and all(
            getattr(self, name) is not None for name in _BAR_NAMES
        )


def _bar(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        log.warning("commitment_intake_bar_invalid", bar=name)
        return None
    if math.isnan(value) or not 0.0 <= value <= 1.0:
        log.warning("commitment_intake_bar_invalid", bar=name)
        return None
    return float(value)


def commitment_intake_surface_config(settings: Any) -> CommitmentIntakeSurfaceConfig:
    config = (
        settings if isinstance(settings, dict) else getattr(settings, "config", None)
    )
    if not isinstance(config, dict):
        return CommitmentIntakeSurfaceConfig()
    system_one = config.get("system_one")
    surfaces = system_one.get("surfaces") if isinstance(system_one, dict) else None
    block = surfaces.get("commitment_intake") if isinstance(surfaces, dict) else None
    if not isinstance(block, dict):
        return CommitmentIntakeSurfaceConfig()
    return CommitmentIntakeSurfaceConfig(
        enabled=block.get("enabled") is True,
        **{name: _bar(block.get(name), name) for name in _BAR_NAMES},
    )


OutcomeKind = Literal[
    "persist_fact",
    "resolve_loop",
    "create_loop_declared",
    "create_loop_suspected",
    "link",
    "hold",
    "fallback",
]
LinkKind = Literal["reminder", "goal"]


@dataclass(frozen=True)
class IntakeOutcome:
    kind: OutcomeKind
    reason: str
    consumed: frozenset[str] = frozenset()
    link_kind: LinkKind | None = None
    family: str | None = None


def _valid_noul(answer: SystemOneAnswer | None) -> bool:
    return (
        answer is not None
        and answer.type == "noul"
        and isinstance(answer.noul, (int, float))
        and not isinstance(answer.noul, bool)
        and not math.isnan(answer.noul)
        and 0.0 <= answer.noul <= 1.0
    )


def _read_choice(
    answer: SystemOneAnswer | None,
) -> tuple[CommitmentChoice, float] | None:
    if answer is None or answer.type != "choice":
        return None
    confidence = answer.confidence
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or math.isnan(confidence)
    ):
        return None
    try:
        return CommitmentChoice(str(answer.choice).strip().lower()), float(confidence)
    except ValueError:
        return None


_INVALID = IntakeOutcome("fallback", "invalid_answer")
_BASE = frozenset({Q_COMMITMENT, Q_RESOLVES})


def decide(
    result: SystemOneResult,
    cfg: CommitmentIntakeSurfaceConfig,
    created: TurnCreation,
    tracked: bool,
) -> IntakeOutcome:
    """Pure merged decision (contract rows 1 to 14). Never raises."""
    try:
        return _decide(result, cfg, created, tracked)
    except Exception as exc:
        log.warning("commitment_decide_failed", error=str(exc))
        return _INVALID


def _decide(
    result: SystemOneResult,
    cfg: CommitmentIntakeSurfaceConfig,
    created: TurnCreation,
    tracked: bool,
) -> IntakeOutcome:
    if result.outcome == "skip":
        return IntakeOutcome("fallback", result.skip_reason or "error")
    read = _read_choice(result.answers.get(Q_COMMITMENT))
    if read is None or not _valid_noul(result.answers.get(Q_RESOLVES)):
        return _INVALID
    if not cfg.calibrated:
        return IntakeOutcome("fallback", "uncalibrated")
    choice, confidence = read
    assert cfg.choice_hold is not None and cfg.resolves_hold is not None

    if float(result.answers[Q_RESOLVES].noul or 0.0) >= cfg.resolves_hold:
        return IntakeOutcome("resolve_loop", "resolves", frozenset({Q_RESOLVES}))
    if created.reminder_id or created.goal_id:
        kind: LinkKind = "reminder" if created.reminder_id else "goal"
        return IntakeOutcome("link", "turn_created", _BASE, link_kind=kind)
    if choice is CommitmentChoice.WAITING_ON:
        return IntakeOutcome("hold", "waiting_on", _BASE)
    if choice in (CommitmentChoice.REMINDER, CommitmentChoice.GOAL):
        if confidence >= cfg.choice_hold:
            return IntakeOutcome("hold", f"{choice.value}_not_created", _BASE)
        return _loop(result, cfg, confidence, tracked, unsure_holds=False)
    if choice is not CommitmentChoice.LOOP and confidence < cfg.choice_hold:
        return IntakeOutcome("hold", "choice_unsure", _BASE)
    if choice is CommitmentChoice.FACT:
        return _fact(result, cfg)
    if choice is not CommitmentChoice.LOOP:
        return IntakeOutcome("hold", choice.value, _BASE)
    return _loop(result, cfg, confidence, tracked)


def _fact(result: SystemOneResult, cfg: CommitmentIntakeSurfaceConfig) -> IntakeOutcome:
    assert cfg.family_hold is not None and cfg.biography_hold is not None
    decision = decide_fact(
        result.answers.get("family"),
        result.answers.get("biography"),
        FactBars(cfg.family_hold, cfg.biography_hold),
    )
    if decision.kind == "skip":
        return _INVALID
    consumed = _BASE | decision.consumed
    if decision.kind == "persist":
        return IntakeOutcome(
            "persist_fact", "persist", consumed, family=decision.family
        )
    return IntakeOutcome("hold", decision.reason, consumed)


def _loop(
    result: SystemOneResult,
    cfg: CommitmentIntakeSurfaceConfig,
    confidence: float,
    tracked: bool,
    *,
    unsure_holds: bool = True,
) -> IntakeOutcome:
    assert cfg.choice_hold is not None and cfg.loop_hold is not None
    assert cfg.explicit_hold is not None
    if unsure_holds and confidence < cfg.choice_hold:
        return IntakeOutcome("hold", "loop_unsure", _BASE)
    if not (
        _valid_noul(result.answers.get(Q_CONCERN))
        and _valid_noul(result.answers.get(Q_EXPLICIT))
    ):
        return _INVALID
    if float(result.answers[Q_CONCERN].noul or 0.0) < cfg.loop_hold:
        return IntakeOutcome("hold", "not_open_concern", _BASE | {Q_CONCERN})
    if tracked:
        return IntakeOutcome("hold", "tracked", _BASE | {Q_CONCERN})
    consumed = _BASE | {Q_CONCERN, Q_EXPLICIT}
    if float(result.answers[Q_EXPLICIT].noul or 0.0) >= cfg.explicit_hold:
        return IntakeOutcome("create_loop_declared", "explicit", consumed)
    return IntakeOutcome("create_loop_suspected", "implied", consumed)
