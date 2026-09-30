"""SystemOneClient protocol — typed judgments (noul / choice / score), not LLM text."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

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
    ) -> SystemOneResult: ...
