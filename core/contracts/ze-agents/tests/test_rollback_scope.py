"""RollbackScope ContextVar and `is_error_result` (Phase 180)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from ze_agents.rollback import (
    RollbackScope,
    current_rollback_scope,
    is_error_result,
    rollback_scope,
)


def test_no_scope_by_default() -> None:
    assert current_rollback_scope() is None


def test_scope_set_and_cleared() -> None:
    scope = RollbackScope(retried_message_id=uuid4())
    with rollback_scope(scope):
        assert current_rollback_scope() is scope
    assert current_rollback_scope() is None


def test_scope_cleared_after_exception() -> None:
    scope = RollbackScope(retried_message_id=uuid4())
    with pytest.raises(RuntimeError):
        with rollback_scope(scope):
            raise RuntimeError("boom")
    assert current_rollback_scope() is None


def test_scope_is_frozen() -> None:
    scope = RollbackScope(retried_message_id=uuid4())
    with pytest.raises(Exception):
        scope.retried_message_id = uuid4()  # type: ignore[misc]


async def test_scope_visible_in_child_task() -> None:
    scope = RollbackScope(retried_message_id=uuid4())

    async def child():
        return current_rollback_scope()

    with rollback_scope(scope):
        assert await asyncio.create_task(child()) is scope


@pytest.mark.parametrize(
    "result,expected",
    [
        ({"error": "nope"}, True),
        ({"ok": False}, True),
        ({"ok": False, "error": "x"}, True),
        ({"status": "error"}, True),
        ({"ok": True}, False),
        ({"status": "done"}, False),
        ({}, False),
        ("some text", False),
        (None, False),
    ],
)
def test_is_error_result(result, expected) -> None:
    assert is_error_result(result) is expected
