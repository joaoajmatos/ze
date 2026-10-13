"""`undo_payload` helper (Phase 180)."""

from __future__ import annotations

import pytest

from ze_agents.errors import AgentConfigError
from ze_agents.tool import undo_payload


def test_returns_scalars_unchanged() -> None:
    assert undo_payload(a="x", b=1, c=1.5, d=True, e=None) == {
        "a": "x",
        "b": 1,
        "c": 1.5,
        "d": True,
        "e": None,
    }


def test_accepts_lists_of_scalars() -> None:
    assert undo_payload(ids=["a", "b"], n=[1, 2]) == {"ids": ["a", "b"], "n": [1, 2]}


def test_empty_payload_is_allowed() -> None:
    assert undo_payload() == {}


@pytest.mark.parametrize(
    "bad",
    [{"x": object()}, {"x": {"nested": 1}}, {"x": [{"a": 1}]}, {"x": [[1]]}, {"x": (1,)}],
)
def test_rejects_non_scalar_values(bad: dict) -> None:
    with pytest.raises(AgentConfigError):
        undo_payload(**bad)
