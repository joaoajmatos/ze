from __future__ import annotations

from ze_core.capability.types import GateDecision, Mode
from ze_core.logging import get_logger

log = get_logger(__name__)

_MODE_TO_DECISION: dict[Mode, GateDecision] = {
    Mode.AUTONOMOUS: GateDecision.EXECUTE,
    Mode.CONFIRM:    GateDecision.AWAIT_CONFIRMATION,
    Mode.DRAFT_ONLY: GateDecision.DRAFT,
    Mode.DISABLED:   GateDecision.BLOCKED,
}

# Maximum GateDecision that a session override may reach for each base mode.
# DISABLED is handled before this table is consulted.
_MODE_CEILING: dict[Mode, GateDecision] = {
    Mode.AUTONOMOUS: GateDecision.EXECUTE,
    Mode.CONFIRM:    GateDecision.EXECUTE,
    Mode.DRAFT_ONLY: GateDecision.DRAFT,
}

# Higher rank = more permissive. Override is allowed only if its rank ≤ ceiling rank.
_DECISION_RANK: dict[GateDecision, int] = {
    GateDecision.BLOCKED:            0,
    GateDecision.DRAFT:              1,
    GateDecision.AWAIT_CONFIRMATION: 2,
    GateDecision.EXECUTE:            3,
}


def _at_or_below_ceiling(ceiling: GateDecision, requested: GateDecision) -> bool:
    return _DECISION_RANK[requested] <= _DECISION_RANK[ceiling]


class CapabilityGate:
    """
    Stateless gate that maps (agent, intent, session_overrides) to a GateDecision.
    Construct once in the container; safe to share across concurrent graph invocations.
    """

    def evaluate(
        self,
        agent: str,
        intent: str,
        session_overrides: dict[str, str],
    ) -> GateDecision:
        from ze_core.errors import UnknownAgentError
        from ze_core.orchestration.registry import get_agent_class

        try:
            agent_cls = get_agent_class(agent)
        except UnknownAgentError:
            log.warning("capability_unknown_agent", agent=agent)
            return GateDecision.AWAIT_CONFIRMATION

        if not getattr(agent_cls, "enabled", True):
            return GateDecision.BLOCKED

        mode: Mode | None = getattr(agent_cls, "capabilities", {}).get(intent)
        if mode is None:
            log.warning("capability_unknown_intent", agent=agent, intent=intent)
            return GateDecision.AWAIT_CONFIRMATION

        if mode == Mode.DISABLED:
            return GateDecision.BLOCKED

        base = _MODE_TO_DECISION[mode]
        ceiling = _MODE_CEILING[mode]

        override_str = session_overrides.get(f"{agent}.{intent}")
        if override_str is None:
            return base

        try:
            override_mode = Mode(override_str)
        except ValueError:
            log.warning("capability_unknown_override_mode", mode=override_str)
            return base

        if override_mode == Mode.DISABLED:
            log.warning("capability_disabled_override_ignored", agent=agent, intent=intent)
            return base

        requested = _MODE_TO_DECISION[override_mode]
        return requested if _at_or_below_ceiling(ceiling, requested) else ceiling
