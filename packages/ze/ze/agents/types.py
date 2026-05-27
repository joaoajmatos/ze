from __future__ import annotations

from dataclasses import dataclass, field

from ze.contacts.types import PersonContext
from ze_core.orchestration.types import AgentContext as _CoreAgentContext
from ze_core.orchestration.types import AgentResult, ToolCall  # noqa: F401 — re-exported

__all__ = ["AgentContext", "AgentResult", "ToolCall"]


@dataclass
class AgentContext(_CoreAgentContext):
    contacts: PersonContext = field(default_factory=PersonContext)
