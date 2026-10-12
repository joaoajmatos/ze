"""Shared fakes for routing-judgment tests: embedder, agents, System One client."""

from __future__ import annotations

from typing import Any

from ze_agents.registry import agent
from ze_agents.system_one import (
    SystemOneAnswer,
    SystemOneQuestion,
    SystemOneResult,
)
from ze_agents.types import AgentContext, AgentResult, Intent, Mode


def register_agent(
    name: str,
    *,
    description: str | None = None,
    intents: dict[str, str] | None = None,
    model: str = "m",
    model_simple: str | None = None,
    routing_criteria: str = "",
) -> None:
    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=name, response="")

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = description or f"The {name} agent"
    _A.routing_criteria = routing_criteria
    _A.enabled = True
    _A.model = model
    _A.model_simple = model_simple
    raw = intents or {"read": "Read"}
    _A.intents = {k: Intent(Mode.AUTONOMOUS, v) for k, v in raw.items()}
    agent(_A)


class _FakeVector:
    def __init__(self, data: list[float]) -> None:
        self._data = data

    def tolist(self) -> list[float]:
        return list(self._data)


class _FakeArray:
    def __init__(self, data: list[list[float]]) -> None:
        self._data = data

    def __matmul__(self, vec: list[float]) -> _FakeVector:
        return _FakeVector([sum(r * v for r, v in zip(row, vec)) for row in self._data])


class FakeEmbedder:
    """Pre-canned vectors; agent order is the router's alphabetical load order."""

    def __init__(self, agent_vecs: dict[str, list[float]], prompt_vec: list[float]):
        self._agent_vecs = agent_vecs
        self._prompt_vec = prompt_vec

    def encode_passage(self, input_: Any, **kwargs: Any) -> _FakeArray:
        names = sorted(self._agent_vecs)
        return _FakeArray([self._agent_vecs[n] for n in names])

    def encode_query(self, input_: str, **kwargs: Any) -> list[float]:
        return self._prompt_vec


def cosine_embedder(scores: dict[str, float]) -> FakeEmbedder:
    """Embedder where each agent's cosine against the prompt is exactly `scores[name]`."""
    names = sorted(scores)
    vecs = {n: [scores[n]] for n in names}
    return FakeEmbedder(vecs, [1.0])


def choice_answer(agent_name: str, peakedness: float) -> SystemOneAnswer:
    return SystemOneAnswer(
        type="choice",
        choice=agent_name,
        confidence=peakedness,
        probabilities={agent_name: peakedness, "none": 1.0 - peakedness},
    )


def ok_result(
    *,
    choice: str | None = None,
    peakedness: float = 0.95,
    noul: float | None = 0.05,
    score: float | None = None,
    model: str = "jev",
) -> SystemOneResult:
    answers: dict[str, SystemOneAnswer] = {}
    if choice is not None:
        answers["agent"] = choice_answer(choice, peakedness)
    if noul is not None:
        answers["multi_specialist"] = SystemOneAnswer(type="noul", noul=noul)
    if score is not None:
        answers["complexity"] = SystemOneAnswer(type="score", score=score)
    return SystemOneResult(
        outcome="ok", model=model, answers=answers, input_tokens=50, latency_ms=30
    )


class FakeSystemOneClient:
    """Records every evaluate call; returns `result` or raises `error`."""

    def __init__(
        self, result: SystemOneResult | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def evaluate(
        self,
        state: str | dict,
        questions: dict[str, SystemOneQuestion],
        *,
        max_attempts: int | None = None,
    ) -> SystemOneResult:
        self.calls.append(
            {"state": state, "questions": questions, "max_attempts": max_attempts}
        )
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result
