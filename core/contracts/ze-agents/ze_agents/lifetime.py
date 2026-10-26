"""Lifetime markers for graph-state fields.

Every field of a graph-state `TypedDict` declares how long its value lives, so the
per-turn reset is generated from the declarations instead of kept in a second list:

- `Turn`: reset at every turn (and at every workflow step) to the declared value.
- `Input`: supplied by whoever starts the turn; the reset leaves it alone.
- `Thread`: kept across turns, with a reason.
- `Run`: kept across the steps of one workflow run, with a reason.

Usage: `judgments: Annotated[list, Turn(factory=list)]`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, get_type_hints

from ze_agents.errors import UndeclaredLifetimeError


@dataclass(frozen=True)
class Turn:
    """Reset every turn. `reset` is an immutable value; `factory` builds a list or dict."""

    reset: Any = None
    factory: Callable[[], Any] | None = None

    def __post_init__(self) -> None:
        if self.factory is not None and self.reset is not None:
            raise UndeclaredLifetimeError(
                "Turn takes either a reset value or a factory, not both"
            )

    def value(self) -> Any:
        return self.factory() if self.factory is not None else self.reset


@dataclass(frozen=True)
class Input:
    """Supplied by whoever starts the turn; the turn reset does not touch it."""


@dataclass(frozen=True)
class Thread:
    reason: str


@dataclass(frozen=True)
class Run:
    reason: str


Lifetime = Turn | Input | Thread | Run
_MARKERS = (Turn, Input, Thread, Run)


def field_lifetimes(td: type) -> dict[str, Lifetime]:
    """Return each field's lifetime marker; raise when a field declares none."""
    hints = get_type_hints(td, include_extras=True)
    lifetimes: dict[str, Lifetime] = {}
    for name, hint in hints.items():
        marker = next(
            (m for m in getattr(hint, "__metadata__", ()) if isinstance(m, _MARKERS)),
            None,
        )
        if marker is None:
            raise UndeclaredLifetimeError(
                f"{td.__name__}.{name} declares no lifetime "
                "(annotate it with Turn, Input, Thread or Run)"
            )
        lifetimes[name] = marker
    return lifetimes


def turn_reset(state_type: type) -> dict[str, Any]:
    """Fresh reset values for every `Turn` field. Never shares a list or dict."""
    return {
        name: marker.value()
        for name, marker in field_lifetimes(state_type).items()
        if isinstance(marker, Turn)
    }
