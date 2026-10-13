"""Rollback scope shared by the executor (ze-core) and the action ledger (ze-memory)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class RollbackScope:
    """Set while a Retry undoes the actions of `retried_message_id`."""

    retried_message_id: UUID


_scope: ContextVar[RollbackScope | None] = ContextVar("rollback_scope", default=None)


def current_rollback_scope() -> RollbackScope | None:
    return _scope.get()


@contextmanager
def rollback_scope(scope: RollbackScope) -> Iterator[RollbackScope]:
    token = _scope.set(scope)
    try:
        yield scope
    finally:
        _scope.reset(token)


def is_error_result(result: Any) -> bool:
    """True when a tool returned an error in its result instead of raising."""
    if not isinstance(result, dict):
        return False
    return (
        "error" in result
        or result.get("ok") is False
        or result.get("status") == "error"
    )
