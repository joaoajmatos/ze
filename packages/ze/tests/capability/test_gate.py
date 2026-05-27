from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_core.capability.gate import CapabilityGate
from ze_core.capability.types import GateDecision, Mode
from ze.logging import configure_logging
from ze.capability.testing import make_gate


@pytest.fixture(autouse=True)
def setup_logging():
    configure_logging()


@pytest.fixture
def gate(config_file):
    g = make_gate(config_file)
    g._persistent_cache = {}
    yield g
    g._restore_registry()


# ── evaluate() — basic decisions ─────────────────────────────────────────────

def test_autonomous_returns_execute(gate):
    assert gate.evaluate("research", "read", {}) == GateDecision.EXECUTE


def test_confirm_returns_await_confirmation(gate):
    assert gate.evaluate("research", "reason", {}) == GateDecision.AWAIT_CONFIRMATION


def test_draft_only_returns_draft(gate):
    assert gate.evaluate("companion", "create", {}) == GateDecision.DRAFT


def test_disabled_agent_returns_blocked(gate):
    assert gate.evaluate("calendar", "read", {}) == GateDecision.BLOCKED


def test_disabled_agent_blocked_regardless_of_override(gate):
    overrides = {"calendar.read": "autonomous"}
    assert gate.evaluate("calendar", "read", overrides) == GateDecision.BLOCKED


def test_unknown_intent_returns_await_confirmation(gate):
    assert gate.evaluate("research", "delete", {}) == GateDecision.AWAIT_CONFIRMATION


def test_unknown_agent_returns_await_confirmation(gate):
    assert gate.evaluate("ghost_agent", "read", {}) == GateDecision.AWAIT_CONFIRMATION


# ── evaluate() — session override escalation ──────────────────────────────────

def test_confirm_escalated_to_execute_by_session(gate):
    overrides = {"research.reason": "autonomous"}
    assert gate.evaluate("research", "reason", overrides) == GateDecision.EXECUTE


def test_autonomous_restricted_to_confirm_by_session(gate):
    overrides = {"research.read": "confirm"}
    assert gate.evaluate("research", "read", overrides) == GateDecision.AWAIT_CONFIRMATION


def test_draft_only_ceiling_blocks_autonomous_override(gate):
    overrides = {"companion.create": "autonomous"}
    assert gate.evaluate("companion", "create", overrides) == GateDecision.DRAFT


def test_draft_only_ceiling_blocks_confirm_override(gate):
    overrides = {"companion.create": "confirm"}
    assert gate.evaluate("companion", "create", overrides) == GateDecision.DRAFT


# ── set_permanent() via DB overrides ─────────────────────────────────────────

@pytest.mark.anyio
async def test_set_permanent_changes_mode(config_file):
    store = MagicMock()
    store.get_all = AsyncMock(return_value={})
    store.set = AsyncMock()
    gate = make_gate(config_file, override_store=store)
    await gate.load_persistent_overrides()

    await gate.set_permanent("research", "reason", Mode.AUTONOMOUS)
    assert gate.evaluate("research", "reason", {}) == GateDecision.EXECUTE
    store.set.assert_awaited_once()


@pytest.mark.anyio
async def test_set_permanent_updates_cache(config_file):
    store = MagicMock()
    store.get_all = AsyncMock(return_value={})
    store.set = AsyncMock()
    gate = make_gate(config_file, override_store=store)
    await gate.load_persistent_overrides()

    await gate.set_permanent("companion", "reason", Mode.CONFIRM)
    assert gate._persistent_cache[("companion", "reason")] == Mode.CONFIRM
