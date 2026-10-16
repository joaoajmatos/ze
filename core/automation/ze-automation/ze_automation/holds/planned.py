"""Plan-time pre-approval of asks-first tools (Phase 181, FR-023/FR-024).

A workflow step or goal milestone names an agent. The asks-first tools of that agent
are what the step may do. The user approves them once, when the plan is created or
edited; an unattended run then calls them without asking. Anything else holds.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable, Sequence
from typing import Any, Protocol

from ze_agents.effects import effect_imperative
from ze_agents.errors import UnknownAgentError
from ze_agents.park import current_approval
from ze_agents.registry import get_agent_class, get_registered_agents
from ze_agents.tool import AskDecision, registered_tools

PLAN_MEMO_TTL_SECONDS = 24 * 3600.0
PLAN_MEMO_MAX_ENTRIES = 32
_FALLBACK_AGENT_NAMES = "research, companion"


class _Planned(Protocol):
    agent_hint: str | None
    approved_writes: list[str]


class PlanMemo:
    """Keeps the plan a user was shown, so approving it runs that exact plan.

    A re-plan by the model may differ from what the user saw. When the memo is gone
    (expired, restart) the creating tool plans again and grants nothing; the run
    then holds for approval instead.
    """

    def __init__(
        self,
        ttl_seconds: float = PLAN_MEMO_TTL_SECONDS,
        max_entries: int = PLAN_MEMO_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._clock = clock
        self._entries: dict[Hashable, tuple[float, Any]] = {}

    def put(self, key: Hashable, value: Any) -> None:
        self._entries.pop(key, None)
        self._entries[key] = (self._clock() + self._ttl, value)
        while len(self._entries) > self._max:
            self._entries.pop(next(iter(self._entries)))

    def get(self, key: Hashable) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry[0] < self._clock():
            self._entries.pop(key, None)
            return None
        return entry[1]

    def take(self, key: Hashable) -> Any | None:
        value = self.get(key)
        self._entries.pop(key, None)
        return value


def memo_of(planner: Any) -> PlanMemo | None:
    memo = getattr(planner, "plan_memo", None)
    return memo if isinstance(memo, PlanMemo) else None


def plan_system_prompt(template: str) -> str:
    """Fill the `{agent_names}` slot of a planner prompt with the registered agents."""
    names = ", ".join(sorted(get_registered_agents())) or _FALLBACK_AGENT_NAMES
    return template.replace("{agent_names}", names)


def planned_writes(step: _Planned) -> list[str]:
    """Asks-first tools of the step's agent; empty without an agent hint."""
    hint = getattr(step, "agent_hint", None)
    if not hint:
        return []
    try:
        cls = get_agent_class(hint)
    except UnknownAgentError:
        return []
    specs = registered_tools()
    names: list[str] = []
    for name in getattr(cls, "tools", None) or []:
        spec = specs.get(name)
        if spec is not None and spec.asks_first and name not in names:
            names.append(name)
    return names


def _effects(tools: Sequence[str]) -> str:
    specs = registered_tools()
    return ", ".join(
        effect_imperative(specs[name].effect_phrase or name) if name in specs else name
        for name in tools
    )


def describe_planned_writes(
    steps: Sequence[_Planned],
    label: str = "Step",
    only_ids: set[str] | None = None,
) -> str:
    """ "Step 2 (messenger) may: send an email" lines; empty when nothing is planned."""
    lines = []
    for index, step in enumerate(steps, start=1):
        if only_ids is not None and getattr(step, "id", "") not in only_ids:
            continue
        tools = planned_writes(step)
        if tools:
            lines.append(f"{label} {index} ({step.agent_hint}) may: {_effects(tools)}")
    return "\n".join(lines)


def plan_writes_check(steps: Sequence[_Planned], label: str = "Step") -> AskDecision:
    """ASK listing what each step may do when any step plans a write, RUN otherwise."""
    text = describe_planned_writes(steps, label)
    return AskDecision.ask(text) if text else AskDecision.run()


def writes_needing_approval(steps: Sequence[Any]) -> list[dict[str, Any]]:
    """Steps whose agent has asks-first tools, as the REST step edit reports them."""
    rows = []
    for step in steps:
        tools = planned_writes(step)
        if tools:
            rows.append(
                {
                    "step_id": getattr(step, "id", ""),
                    "agent": step.agent_hint,
                    "tools": tools,
                }
            )
    return rows


def approval_given() -> bool:
    """True while a tool body runs under the user's approval of this exact call."""
    approval = current_approval.get()
    return bool(approval) and approval.get("outcome") in ("approved", "edited")


def grant_planned_writes(steps: Sequence[_Planned]) -> None:
    for step in steps:
        step.approved_writes = planned_writes(step)
