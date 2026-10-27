"""Judgment surface — what every System One judgment point repeats.

A surface declares its questions, state builder, bars and pure ``decide()``. This
module reads ``system_one.surfaces.<name>``, applies the calibrated rule, makes the
single-attempt call, maps an exception to a skip and builds the record the trace
rows come from.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, ClassVar, Literal, Self, TypeVar

from ze_logging import get_logger

from ze_agents.system_one import (
    QuestionKind,
    SystemOneClient,
    SystemOneQuestion,
    SystemOneResult,
)

log = get_logger(__name__)

NotAsked = Literal["disabled", "uncalibrated", "unavailable"]

D = TypeVar("D")


@dataclass(frozen=True)
class SurfaceBar:
    name: str
    value: float


@dataclass(frozen=True)
class DecisionUse:
    consumed: frozenset[str]
    unused_reason: str | None = None


@dataclass(frozen=True)
class SurfaceConfig:
    enabled: bool = False

    SURFACE: ClassVar[str]
    BARS: ClassVar[Mapping[str, str]] = {}
    EXTRAS: ClassVar[Mapping[str, Callable[[Any], Any]]] = {}

    @classmethod
    def from_settings(cls, settings: Any) -> Self:
        block = surface_block(settings, cls.SURFACE)
        if block is None:
            return cls()
        bars = {
            name: parse_bar(block.get(name), name, surface=cls.SURFACE)
            for name in cls.BARS
        }
        extras = {name: parse(block.get(name)) for name, parse in cls.EXTRAS.items()}
        return cls(enabled=block.get("enabled") is True, **bars, **extras)

    def consistent(self) -> bool:
        return True

    @property
    def calibrated(self) -> bool:
        return (
            self.enabled
            and all(getattr(self, name) is not None for name in self.BARS)
            and self.consistent()
        )

    def bar_for(self, question_id: str) -> SurfaceBar | None:
        for name, governed in self.BARS.items():
            if governed == question_id:
                value = getattr(self, name)
                return None if value is None else SurfaceBar(name, value)
        return None


@dataclass(frozen=True)
class Judgment:
    surface: str
    result: SystemOneResult
    question_kinds: dict[str, QuestionKind]
    consumed: frozenset[str]
    skip_reason: str | None
    bars: dict[str, SurfaceBar | None]


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


def parse_bar(value: Any, name: str, *, surface: str) -> float | None:
    """A bar in [0, 1], or ``None`` when unset or invalid (invalid warns once per process)."""
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or math.isnan(value)
        or not 0.0 <= value <= 1.0
    ):
        _warn_bar_invalid(surface, name)
        return None
    return float(value)


def gate(cfg: SurfaceConfig, client: SystemOneClient | None) -> NotAsked | None:
    """Why the surface may not ask, or ``None`` when it may."""
    if not cfg.enabled:
        return "disabled"
    if not cfg.calibrated:
        _warn_uncalibrated(cfg.SURFACE)
        return "uncalibrated"
    if client is None:
        return "unavailable"
    return None


async def judge(
    client: SystemOneClient,
    cfg: SurfaceConfig,
    state: str | dict,
    questions: Mapping[str, SystemOneQuestion],
    decide: Callable[[SystemOneResult], D],
    read: Callable[[D], DecisionUse],
) -> tuple[Judgment, D]:
    """One single-attempt request, then the surface's own ``decide`` over the result."""
    raised = False
    try:
        result = await client.evaluate(state, dict(questions), max_attempts=1)
    except Exception as exc:
        log.warning("system_one_judgment_error", surface=cfg.SURFACE, error=str(exc))
        result = SystemOneResult(outcome="skip", skip_reason="error")
        raised = True
    decision = decide(result)
    use = read(decision)
    if raised:
        skip_reason: str | None = "error"
    elif result.outcome == "skip":
        skip_reason = result.skip_reason
    else:
        skip_reason = use.unused_reason
    record = Judgment(
        surface=cfg.SURFACE,
        result=result,
        question_kinds={qid: q.type for qid, q in questions.items()},
        consumed=use.consumed,
        skip_reason=skip_reason,
        bars={qid: cfg.bar_for(qid) for qid in questions},
    )
    return record, decision


def reset_surface_warnings() -> None:
    """Forget which surfaces and bars already warned (tests only)."""
    _warn_uncalibrated.cache_clear()
    _warn_bar_invalid.cache_clear()


@lru_cache(maxsize=None)
def _warn_uncalibrated(surface: str) -> None:
    log.warning("system_one_surface_uncalibrated", surface=surface)


@lru_cache(maxsize=None)
def _warn_bar_invalid(surface: str, bar: str) -> None:
    log.warning("system_one_bar_invalid", surface=surface, bar=bar)
