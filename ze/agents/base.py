import json
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncIterator

from ze.agents.identity import build_identity_block
from ze.agents.tool import ToolAccess, get_tool
from ze.agents.types import AgentContext, AgentResult, ToolCall
from ze.capability.types import GateDecision
from ze.errors import ToolBlockedError, ZeError
from ze.logging import get_logger
from ze.settings import Settings

if TYPE_CHECKING:
    from ze.openrouter.client import OpenRouterClient


class BaseAgent(ABC):
    name: str           # set by subclass as a class attribute
    tools: list[str] = []  # names of tools this agent may call

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._log = get_logger(__name__)

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentResult:
        """Execute the agent and return a complete result."""

    @abstractmethod
    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        """Stream response tokens."""
        raise NotImplementedError
        yield  # make mypy happy

    # ── Lifecycle (optional override) ─────────────────────────────────────────

    async def startup(self) -> None:
        """Called once at app startup after DI wiring. Override for warmup."""

    async def shutdown(self) -> None:
        """Called during app shutdown. Override for cleanup."""

    # ── Tool execution ────────────────────────────────────────────────────────

    async def call_tool(self, name: str, ctx: AgentContext, **kwargs) -> ToolCall:
        """Execute a registered tool with capability enforcement.

        READ tools execute in any gate state.
        WRITE tools are suppressed and return a draft ToolCall when gate is DRAFT.
        Any tool raises ToolBlockedError when gate is BLOCKED.
        """
        spec = get_tool(name)

        if ctx.gate_decision == GateDecision.BLOCKED:
            raise ToolBlockedError(
                f"Tool {name!r} is blocked by the capability gate"
            )

        if spec.access == ToolAccess.WRITE and ctx.gate_decision == GateDecision.DRAFT:
            self._log.info("tool_suppressed_draft", tool=name, agent=self.name)
            return ToolCall(
                tool_name=name,
                args=kwargs,
                result=None,
                duration_ms=0,
                success=False,
                error="suppressed: draft mode",
                is_draft=True,
            )

        self._log.debug("tool_start", tool=name, agent=self.name, access=spec.access.value)
        start = time.monotonic()
        try:
            result = await spec.fn(**kwargs)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            self._log.warning("tool_error", tool=name, agent=self.name, error=str(exc))
            return ToolCall(
                tool_name=name,
                args=kwargs,
                result=None,
                duration_ms=duration_ms,
                success=False,
                error=str(exc),
            )

        self._log.info(
            "tool_complete",
            tool=name,
            agent=self.name,
            success=result.success,
            duration_ms=result.duration_ms,
        )
        return result

    # ── Agentic tool loop ─────────────────────────────────────────────────────

    async def agentic_loop(
        self,
        ctx: AgentContext,
        client: "OpenRouterClient",
        messages: list[dict],
        system: str,
        deps: dict[str, Any],
        tool_names: list[str] | None = None,
        max_iterations: int = 6,
        max_history_tokens: int | None = None,
    ) -> tuple[str, list[ToolCall]]:
        """Drive a ReAct loop: LLM picks tools, Ze dispatches them, loop until text.

        Args:
            ctx:            Agent context — passed to call_tool() for gate checks.
            client:         OpenRouter client to use for LLM calls.
            messages:       Conversation history including current user turn.
                            Mutated in-place as tool turns are appended.
            system:         System prompt.
            deps:           Ze-internal dep map injected per tool (e.g. {"client": tavily}).
            tool_names:     Which tools to expose; defaults to self.tools.
            max_iterations: Max tool-call rounds before forcing a plain completion.
            max_history_tokens: If set, oldest role="tool" messages are dropped when the
                                approximate token count of messages exceeds this budget.
                                The system prompt and last 4 messages are never removed.
        """
        names = tool_names if tool_names is not None else self.tools
        tool_schemas = [get_tool(n).llm_schema() for n in names]
        accumulated: list[ToolCall] = []

        for iteration in range(max_iterations):
            if max_history_tokens is not None:
                _truncate_messages(messages, max_history_tokens)

            text, tool_calls = await client.complete_with_tools(
                messages=messages,
                model=self._model(ctx),
                tools=tool_schemas,
                system=system,
            )

            if text is not None:
                self._log.debug(
                    "agentic_loop_done",
                    agent=self.name,
                    iterations=iteration + 1,
                    tool_calls=len(accumulated),
                )
                return text, accumulated

            # Append the assistant turn (with tool call requests) to history
            assert tool_calls is not None
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in tool_calls
                ],
            })

            # Execute each tool call and append the result turn
            for tc in tool_calls:
                merged = _merge_deps(tc["name"], tc["arguments"], deps)
                tool_call = await self.call_tool(tc["name"], ctx, **merged)
                accumulated.append(tool_call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": _serialise_result(tool_call),
                })

        # max_iterations reached — force a plain text response without tools
        self._log.warning(
            "agentic_loop_max_iterations",
            agent=self.name,
            max_iterations=max_iterations,
        )
        text = await client.complete(
            messages=messages,
            model=self._model(ctx),
            system=system,
        )
        return text, accumulated

    # ── Config helpers ────────────────────────────────────────────────────────

    def _model(self, ctx: AgentContext | None = None) -> str:
        if ctx is not None and ctx.model is not None:
            return ctx.model
        return self._settings.agent_configs.get(self.name, {}).get(
            "model", "anthropic/claude-sonnet-4-5"
        )

    def _timeout(self) -> int:
        return int(
            self._settings.agent_configs.get(self.name, {}).get("timeout", 30)
        )

    async def emit(self, ctx: AgentContext, key: str, **kwargs: str) -> None:
        """Emit a localized progress message if a reporter is attached."""
        if ctx.reporter is not None:
            await ctx.reporter.emit(key, **kwargs)

    def _format_memory(self, ctx: AgentContext) -> str:
        lines = [f"- {f.key}: {f.value}" for f in ctx.memory.facts]
        return "\n".join(lines) if lines else "(none)"

    def _format_contacts(self, ctx: AgentContext) -> str:
        lines = []
        for p in ctx.contacts.people:
            line = f"- {p.name}: {p.relationship_to_user}"
            if p.notes:
                line += f" ({p.notes})"
            lines.append(line)
        return "\n".join(lines)

    def _build_system_prompt(
        self,
        agent_instructions: str,
        ctx: AgentContext,
        **extra: str,
    ) -> str:
        """Compose the full system prompt: shared identity block + agent instructions."""
        identity = build_identity_block(
            ctx.persona if ctx.persona else self._settings.active_profile(),
            self._format_memory(ctx),
            profile=ctx.memory.profile,
            contacts_context=self._format_contacts(ctx),
        )
        rendered = agent_instructions.format(**extra) if extra else agent_instructions
        return f"{identity}\n\n{rendered}"


# ── Module-level helpers used by agentic_loop ─────────────────────────────────

def _merge_deps(tool_name: str, llm_args: dict, deps: dict[str, Any]) -> dict:
    """Merge LLM-provided args with Ze-internal deps for a tool call.

    For each param in the tool spec that is absent from llm_args, inject from
    deps by param name. Unknown params not in deps are left out (call_tool will
    receive them only if the LLM supplied them).
    """
    from ze.agents.tool import get_tool
    spec = get_tool(tool_name)
    merged = dict(llm_args)
    for param in spec.params:
        if param.name not in merged and param.name in deps:
            merged[param.name] = deps[param.name]
    return merged


def _serialise_result(tc: ToolCall) -> str:
    """Convert a ToolCall result to a string for inclusion in a tool message."""
    if not tc.success:
        return f"[error: {tc.error}]"
    if tc.result is None:
        return "[no result]"
    if isinstance(tc.result, str):
        return tc.result
    try:
        return json.dumps(tc.result)
    except (TypeError, ValueError):
        return str(tc.result)


def _truncate_messages(messages: list[dict], max_tokens: int) -> None:
    """Remove oldest role='tool' messages until total token estimate is under budget.

    The last 4 messages are never removed regardless of budget.
    Token estimate: len(json.dumps(msg)) // 4 per message.
    """
    while True:
        total = sum(len(json.dumps(m)) // 4 for m in messages)
        if total <= max_tokens:
            break

        protected_from = max(0, len(messages) - 4)
        removed = False
        for i in range(protected_from):
            if messages[i].get("role") == "tool":
                messages.pop(i)
                removed = True
                break

        if not removed:
            break
