from __future__ import annotations

from dataclasses import fields

import pytest

from ze_agents import derive
from ze_agents.derive import DERIVATION, KINDS, Given, Inherit, Reset
from ze_agents.errors import UndeclaredDerivationError
from ze_agents.types import AgentContext


def test_every_agent_context_field_has_a_row() -> None:
    declared = set(DERIVATION)
    actual = {f.name for f in fields(AgentContext)}
    assert declared == actual, (
        f"missing a DERIVATION row: {sorted(actual - declared)}; "
        f"row for no field: {sorted(declared - actual)}"
    )


def test_every_rule_is_well_formed() -> None:
    for name, row in DERIVATION.items():
        for kind in KINDS:
            rule = getattr(row, kind)
            assert isinstance(rule, (Inherit, Given, Reset)), (name, kind)
            if isinstance(rule, Reset):
                assert rule.reason.strip(), f"{name}.{kind} Reset has no reason"
            if isinstance(rule, Given):
                assert rule.source.strip(), f"{name}.{kind} Given has no source"


def test_an_operation_names_a_field_with_no_row(monkeypatch) -> None:
    rows = {k: v for k, v in DERIVATION.items() if k != "timezone"}
    monkeypatch.setattr(derive, "DERIVATION", rows)
    with pytest.raises(UndeclaredDerivationError, match="timezone"):
        derive.for_action("s")


def test_loop_active_is_never_inherited() -> None:
    row = DERIVATION["write_gate"]
    assert isinstance(row.delegate, Inherit)
    assert isinstance(row.subtask, Given)
