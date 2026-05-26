from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from ze_core.capability.types import Mode
from ze_core.orchestration.types import AgentContext, AgentResult


class BaseAgent(ABC):
    name: str
    description: str
    model: str = "anthropic/claude-sonnet-4-5"
    model_simple: str | None = None
    vision_capable: bool = False
    timeout: int = 30
    enabled: bool = True
    capabilities: dict[str, Mode] = {}
    intent_map: dict[str, str] = {}
    tools: list[str] = []

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentResult:
        """Execute the agent and return a complete result."""

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        """Stream response tokens. Default raises NotImplementedError."""
        raise NotImplementedError
        yield  # make type checkers happy

    async def startup(self) -> None:
        """Called once after DI wiring. Override for warmup."""

    async def shutdown(self) -> None:
        """Called during app shutdown. Override for cleanup."""
