from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ze_core.capability.types import GateDecision
from ze_core.memory.types import MemoryContext  # re-exported for AgentContext consumers
from ze_core.progress.reporter import ProgressReporter


class IdentityBuilder(Protocol):
    """Callable that renders the persona/memory preamble injected into agent prompts."""

    def __call__(
        self,
        persona: dict,
        memory_context: str,
        *,
        profile: Any,
        contacts_context: str,
    ) -> str: ...


@dataclass
class ToolCall:
    tool_name: str
    args: dict[str, Any]
    result: Any
    duration_ms: int
    success: bool
    error: str | None = None
    is_draft: bool = False


@dataclass
class AgentContext:
    session_id: str
    prompt: str
    intent: str
    gate_decision: GateDecision = GateDecision.EXECUTE
    memory: MemoryContext = field(default_factory=MemoryContext)
    contacts: Any = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    persona: dict = field(default_factory=dict)
    model: str | None = None
    reporter: ProgressReporter | None = field(default=None, repr=False)
    # identity_builder is runtime-only (a callable); always None in stored state.
    # Never checkpoint a context where this is set — the serde test enforces that.
    identity_builder: IdentityBuilder | None = field(default=None, repr=False)
    # extensions must hold only msgpack-serializable primitives so stored contexts
    # can be checkpointed. Use identity_builder for callable injection instead.
    extensions: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass
class AgentResult:
    agent: str
    response: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_used: int = 0
    memory_proposals: list = field(default_factory=list)
    contact_proposals: list = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)
