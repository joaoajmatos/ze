from __future__ import annotations

from typing import Annotated, TypedDict

import pytest

from ze_agents.errors import UndeclaredLifetimeError
from ze_agents.lifetime import Input, Run, Thread, Turn, field_lifetimes, turn_reset


class _Declared(TypedDict):
    prompt: Annotated[str, Input()]
    judgments: Annotated[list, Turn(factory=list)]
    index: Annotated[dict, Turn(factory=dict)]
    flag: Annotated[bool, Turn(reset=False)]
    final: Annotated["str | None", Turn()]
    messages: Annotated[list[dict], Thread("history outlives the turn")]
    steps: Annotated[list, Run("kept across one workflow run")]


class _Other(TypedDict):
    extra: Annotated[list, Turn(factory=list)]
    kept: Annotated[int, Run("run counter")]


class _Unmarked(TypedDict):
    prompt: Annotated[str, Input()]
    stray: list


def test_field_lifetimes_returns_each_marker():
    lifetimes = field_lifetimes(_Declared)
    assert isinstance(lifetimes["prompt"], Input)
    assert isinstance(lifetimes["judgments"], Turn)
    assert isinstance(lifetimes["messages"], Thread)
    assert isinstance(lifetimes["steps"], Run)
    assert lifetimes["messages"].reason == "history outlives the turn"


def test_unmarked_field_names_class_and_field():
    with pytest.raises(UndeclaredLifetimeError) as err:
        field_lifetimes(_Unmarked)
    assert "_Unmarked" in str(err.value)
    assert "stray" in str(err.value)


def test_turn_reset_returns_only_turn_keys():
    reset = turn_reset(_Declared)
    assert reset == {
        "judgments": [],
        "index": {},
        "flag": False,
        "final": None,
    }


def test_turn_reset_omits_input_thread_and_run():
    reset = turn_reset(_Declared)
    for key in ("prompt", "messages", "steps"):
        assert key not in reset


def test_turn_reset_never_shares_mutable_values():
    first = turn_reset(_Declared)
    first["judgments"].append("x")
    first["index"]["k"] = 1
    second = turn_reset(_Declared)
    assert second["judgments"] == []
    assert second["index"] == {}


def test_merged_typed_dict_resolves_both_bases():
    merged = type("M", (_Declared, _Other), {"__annotations__": {}})
    lifetimes = field_lifetimes(merged)
    assert isinstance(lifetimes["kept"], Run)
    reset = turn_reset(merged)
    assert reset["extra"] == []
    assert reset["judgments"] == []
    assert "kept" not in reset


def test_turn_with_both_reset_and_factory_is_rejected():
    with pytest.raises(UndeclaredLifetimeError):
        Turn(reset=1, factory=list)


def test_turn_rejects_a_mutable_reset_value():
    with pytest.raises(UndeclaredLifetimeError):
        Turn(reset=[])
