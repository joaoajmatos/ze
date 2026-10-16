"""FR-004: every proactive push is a registered kind, sent through notify()."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from ze_proactive.push_kinds import registered_push_kinds

REPO = Path(__file__).resolve().parents[3]

KIND_MODULES = [
    "ze_api.wiring.push_kinds",
    "ze_automation.push_kinds",
    "ze_worldstate.push_kinds",
    "ze_correlation.push_kinds",
    "ze_proactive.push_kinds",
    "ze_personal.push_kinds",
    "ze_finance.push_kinds",
    "ze_messenger.push_kinds",
    "ze_calendar.push_kinds",
    "ze_workspace.push_kinds",
]

R, A, D = "requested", "accountability", "discretionary"
EXPECTED: dict[str, tuple[str, str]] = {
    "user_reminder": (R, "high"),
    "calendar_reminder": (R, "high"),
    "confirmation_request": (A, "high"),
    "confirmation_timeout": (A, "low"),
    "workspace_run_completed": (A, "normal"),
    "workflow_failure": (A, "high"),
    "goal_plan_proposed": (A, "high"),
    "goal_attention_needed": (A, "high"),
    "goal_plan_adapted": (A, "normal"),
    "goal_milestone_done": (A, "normal"),
    "goal_completed": (A, "normal"),
    "goal_gate": (A, "high"),
    "cost_anomaly": (A, "high"),
    "accountability_narrative": (A, "normal"),
    "goal_narrative": (A, "normal"),
    "morning_brief": (A, "normal"),
    "calendar_reminders_scheduled": (A, "low"),
    "loop_drift": (D, "normal"),
    "hypothesis": (D, "normal"),
    "stuck_goal": (D, "normal"),
    "goal_suggestion": (D, "normal"),
    "goal_overlap": (D, "normal"),
    "goal_reuse": (D, "low"),
    "insight": (D, "normal"),
    "contact_review": (D, "low"),
    "finance_stale_nudge": (D, "low"),
    "finance_recurring_new": (D, "normal"),
    "finance_price_change": (D, "normal"),
    "inbound_message": (D, "normal"),
    "quiet_hours_summary": (A, "normal"),
    "write_approval_held": (R, "normal"),
}


def test_registry_matches_spec_inventory():
    for module in KIND_MODULES:
        importlib.import_module(module)
    registry = {
        k.event_type: (k.push_class, k.urgency)
        for k in registered_push_kinds().values()
        if k.source != "tests"
    }
    assert registry == EXPECTED
    assert len(EXPECTED) == 31


SCAN_ROOTS = ["core", "plugins", "apps/ze-api/ze_api"]
ALLOWED = {
    "core/contracts/ze-proactive/ze_proactive/notifier.py",
    "apps/ze-api/ze_api/interface/native.py",
}
BANNED_ATTRS = {"push", "push_notification"}


def _violations(source: str, rel: str) -> list[str]:
    if rel in ALLOWED:
        return []
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in BANNED_ATTRS
        ):
            continue
        receiver = ast.unparse(node.func.value)
        if "notifier" in receiver or "interface" in receiver:
            found.append(f"{rel}:{node.lineno} {receiver}.{node.func.attr}(...)")
    return found


def _source_files():
    for root in SCAN_ROOTS:
        for path in (REPO / root).rglob("*.py"):
            parts = path.relative_to(REPO).parts
            if "tests" in parts or ".venv" in parts or "node_modules" in parts:
                continue
            yield path


def test_no_direct_push_calls_outside_the_governor():
    violations: list[str] = []
    for path in _source_files():
        rel = path.relative_to(REPO).as_posix()
        violations += _violations(path.read_text(), rel)
    assert violations == []


@pytest.mark.parametrize(
    "line",
    ["await self._notifier.push('x')", "await interface.push_notification(n)"],
)
def test_scan_detects_a_dummy_push(line):
    assert _violations(f"async def f():\n    {line}\n", "plugins/x/y.py")
