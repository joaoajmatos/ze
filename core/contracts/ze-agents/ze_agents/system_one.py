"""SystemOneClient protocol — typed judgments (noul / choice / score), not LLM text."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from ze_logging import get_logger

log = get_logger(__name__)

QuestionKind = Literal["noul", "choice", "score"]
SkipReason = Literal[
    "disabled",
    "missing_key",
    "timeout",
    "overload",
    "error",
    "invalid_request",
]
ResultOutcome = Literal["ok", "skip"]


@dataclass
class SystemOneQuestion:
    type: QuestionKind
    instructions: str
    criteria: dict[str, str] | list[str] | None = None

    def to_wire(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "instructions": self.instructions,
        }
        if self.criteria is not None:
            payload["criteria"] = self.criteria
        return payload


@dataclass
class SystemOneAnswer:
    type: QuestionKind
    noul: float | None = None
    choice: str | None = None
    score: float | None = None
    probabilities: dict[str, float] | None = None
    confidence: float | None = None


@dataclass
class SystemOneResult:
    outcome: ResultOutcome
    skip_reason: SkipReason | None = None
    model: str | None = None
    provider: str | None = None
    id: str | None = None
    answers: dict[str, SystemOneAnswer] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0


@runtime_checkable
class SystemOneClient(Protocol):
    async def evaluate(
        self,
        state: str | dict,
        questions: dict[str, SystemOneQuestion],
        *,
        max_attempts: int | None = None,
    ) -> SystemOneResult: ...


def surface_block(settings: Any, surface: str) -> dict | None:
    """``system_one.surfaces.<surface>`` from a config dict or a settings object, else ``None``."""
    config = (
        settings if isinstance(settings, dict) else getattr(settings, "config", None)
    )
    if not isinstance(config, dict):
        return None
    system_one = config.get("system_one")
    surfaces = system_one.get("surfaces") if isinstance(system_one, dict) else None
    block = surfaces.get(surface) if isinstance(surfaces, dict) else None
    return block if isinstance(block, dict) else None


def parse_bar(value: Any, name: str, *, event: str) -> float | None:
    """A bar in [0, 1], or ``None`` when unset or invalid (invalid logs ``event``)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        log.warning(event, bar=name)
        return None
    if math.isnan(value) or not 0.0 <= value <= 1.0:
        log.warning(event, bar=name)
        return None
    return float(value)


def valid_noul(answer: SystemOneAnswer | None, *, unit_range: bool = True) -> bool:
    """A Noul answer carrying a real number; ``unit_range`` also requires it in [0, 1]."""
    if (
        answer is None
        or answer.type != "noul"
        or isinstance(answer.noul, bool)
        or not isinstance(answer.noul, (int, float))
        or math.isnan(answer.noul)
    ):
        return False
    return not unit_range or 0.0 <= answer.noul <= 1.0


def valid_choice(
    answer: SystemOneAnswer | None, options: Sequence[str] | None = None
) -> bool:
    """A Choice answer with a choice and a confidence, and the choice among ``options`` if given."""
    return (
        answer is not None
        and answer.type == "choice"
        and answer.choice is not None
        and answer.confidence is not None
        and (options is None or answer.choice in options)
    )
