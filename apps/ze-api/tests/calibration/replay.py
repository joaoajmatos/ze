"""Deterministic stand-ins for the calibration runners' network and model dependencies.

``ReplayClient`` answers every System One request from a hash of the state and the question id,
``HashEmbedder`` stands in for the E5 singleton and ``FakeHaiku`` for the loop-gate baseline's
LLM client. The golden checks run every runner against them, so the output is reproducible
and nothing is spent.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
from ze_agents.system_one import (
    SystemOneAnswer,
    SystemOneQuestion,
    SystemOneResult,
)

MODEL = "replay"
EMBED_DIM = 64
EMBED_OFFSET = 0.35


def _digest(*parts: str) -> bytes:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).digest()


def _unit(seed: bytes, index: int) -> float:
    """A float in [0, 1) from the seed, stable across runs and Python versions."""
    raw = hashlib.sha256(seed + index.to_bytes(2, "big")).digest()
    return int.from_bytes(raw[:6], "big") / float(1 << 48)


def _state_text(state: str | dict) -> str:
    return (
        state
        if isinstance(state, str)
        else json.dumps(state, sort_keys=True, default=str)
    )


def _keys(criteria: dict[str, str] | list[str] | None) -> list[str]:
    return sorted(criteria or [])


class ReplayClient:
    """A ``SystemOneClient`` whose answers are a pure function of ``(state, question_id)``."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._model = kwargs.get("model", MODEL)

    async def evaluate(
        self,
        state: str | dict,
        questions: dict[str, SystemOneQuestion],
        *,
        max_attempts: int | None = None,
    ) -> SystemOneResult:
        text = _state_text(state)
        answers = {qid: self._answer(text, qid, q) for qid, q in questions.items()}
        seed = _digest(text, "latency")
        return SystemOneResult(
            outcome="ok",
            model=MODEL,
            answers=answers,
            latency_ms=100 + int(_unit(seed, 0) * 800),
        )

    @staticmethod
    def _answer(text: str, qid: str, question: SystemOneQuestion) -> SystemOneAnswer:
        seed = _digest(text, qid)
        if question.type == "noul":
            return SystemOneAnswer(type="noul", noul=round(_unit(seed, 0), 4))
        if question.type == "score":
            return SystemOneAnswer(type="score", score=round(_unit(seed, 0), 4))
        keys = _keys(question.criteria)
        winner = int(_unit(seed, 1) * len(keys))
        confidence = round(0.5 + 0.5 * _unit(seed, 2), 4)
        rest = [_unit(seed, 10 + i) + 0.01 for i in range(len(keys))]
        rest[winner] = 0.0
        scale = (1.0 - confidence) / sum(rest) if sum(rest) else 0.0
        probabilities = {
            k: round(w * scale, 4) if i != winner else confidence
            for i, (k, w) in enumerate(zip(keys, rest))
        }
        return SystemOneAnswer(
            type="choice",
            choice=keys[winner],
            probabilities=probabilities,
            confidence=confidence,
        )


class HashEmbedder:
    """E5's query/passage interface over SHA-256 vectors: same text, same unit vector."""

    @staticmethod
    def _vector(text: str) -> np.ndarray:
        raw = _digest(text) + _digest(text, "tail")
        vec = np.frombuffer(raw, dtype=np.uint8)[:EMBED_DIM] / 255.0 - EMBED_OFFSET
        return vec / np.linalg.norm(vec)

    def encode_query(
        self, text: str, normalize_embeddings: bool = True, **_: Any
    ) -> np.ndarray:
        return self._vector(f"query: {text}")

    def encode_passage(
        self, text: str | list[str], normalize_embeddings: bool = True, **_: Any
    ) -> np.ndarray:
        if isinstance(text, list):
            return np.stack([self._vector(f"passage: {t}") for t in text])
        return self._vector(f"passage: {text}")


class FakeHaiku:
    """The loop-gate baseline's LLM client: a deterministic gate reply per input text."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def complete(self, messages: list[dict[str, str]], **_: Any) -> str:
        seed = _digest(messages[-1]["content"], "haiku")
        is_loop = _unit(seed, 0) < 0.45
        resolves = not is_loop and _unit(seed, 1) < 0.15
        reply = {
            "is_loop": is_loop,
            "title": "replay title" if is_loop or resolves else "",
            "explicit_declaration": is_loop and _unit(seed, 2) < 0.4,
            "resolves_existing": resolves,
        }
        body = json.dumps(reply)
        return f"```json\n{body}\n```" if _unit(seed, 3) < 0.5 else body

    async def aclose(self) -> None:
        return None
