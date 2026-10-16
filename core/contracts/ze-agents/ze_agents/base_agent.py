from __future__ import annotations

import json
import time
from dataclasses import dataclass
from uuid import uuid4
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from functools import cached_property
from typing import Any, AsyncIterator

from ze_agents.client import LLMClient
from ze_agents.defaults import MODEL_AGENT_DEFAULT, MODEL_AGENT_TIMEOUT
from ze_agents.errors import (
    AgentAbortedError,
    AgentConfigError,
    AgentError,
    HookAbort,
    LoopParked,
)
from ze_agents.hooks import (
    LoopEndEvent,
    LoopStartEvent,
    ToolEndEvent,
    ToolStartEvent,
    get_hooks,
)
from ze_agents.park import (
    DECLINED_RESULT,
    MAX_WRITE_ROUNDS,
    OVER_CAP_RESULT,
    ParkedLoop,
    ParkedWrite,
    ParkReason,
    current_approval,
    generic_summary,
)
from ze_agents.interrupt import (
    workspace_thread_id,
)
from ze_logging import get_logger
from ze_agents.types import (
    AgentContext,
    AgentResult,
    RetrievalRequest,
    Source,
    ToolCall,
    add_sources,
)

# Schemas for OpenRouter server-side tools (executed by OpenRouter, not the client).
_OPENROUTER_TOOL_SCHEMAS: dict[str, dict] = {
    "openrouter:web_search": {"type": "openrouter:web_search"},
}

# Platform tools merged into every agent unless `workspace_opt_out` is set.
# Names only — registration lives in ze_workspace.tools / ze_skills.tools;
# unknown names are skipped.
_PLATFORM_TOOLS = (
    "workspace_list",
    "workspace_read",
    "workspace_write",
    "workspace_delete",
    "workspace_run",
    "workspace_run_skill_script",
    "ingest_workspace_file",
    "workspace_reset",
    "list_skills",
)
_PROCEDURE_INVOKE_TOOL = "invoke_procedure"

log = get_logger(__name__)

RETRY_WRITE_REFUSAL = (
    "This is a retry of an earlier reply, so tools that change things are "
    "switched off. Do not claim the action happened. Say in words what you "
    "would do and offer to do it as a normal request."
)

MEMORY_CONSTITUTION = (
    "## Memory constitution\n"
    "Use retrieved facts silently when they change the answer. "
    "Do not recite them unsolicited and do not say you remember something "
    "unless the user asked what you know. "
    "Treat inferred, low-confidence, or stale lines as approximate. "
    "Never invent identity that is not in the biography block.\n"
)

BIOGRAPHY_HEADING = "## Retrieved biography"

_DEFERRED_DELEGATE_RESULT = (
    "Not run yet: another delegated action is waiting for the user's approval. "
    "Ask again after it is answered."
)


def _fact_origin(provenance: Any) -> str:
    key = provenance.value if hasattr(provenance, "value") else str(provenance or "")
    key = key.lower()
    if key in {"synthesized"}:
        return "inferred"
    if key in {"prompt_supplied", ""}:
        return "user-stated"
    return key.replace("_", "-")


def _format_fact_recency(created_at: Any) -> str:
    if created_at is None:
        return "recency unknown"
    when = created_at
    if getattr(when, "tzinfo", None) is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - when
    days = max(0, int(delta.total_seconds() // 86400))
    if days == 0:
        return "stored today"
    if days == 1:
        return "stored 1d ago"
    return f"stored {days}d ago"


def _split_identity(identity: str) -> tuple[str, str]:
    marker = f"\n{BIOGRAPHY_HEADING}\n"
    if marker in identity:
        persona, biography = identity.split(marker, 1)
        return persona.strip(), biography.strip()
    if identity.startswith(BIOGRAPHY_HEADING):
        return "", identity[len(BIOGRAPHY_HEADING) :].strip()
    return identity.strip(), ""


def _is_openrouter_server_tool(name: str) -> bool:
    """Return True for OpenRouter-native tools that are not in the local @tool registry."""
    if name in _OPENROUTER_TOOL_SCHEMAS:
        return True
    return name == "openrouter" or name.startswith(("openrouter:", "openrouter_"))


def _canonical_openrouter_tool_name(name: str) -> str:
    """Normalize variant OpenRouter tool names returned by the API."""
    if name in _OPENROUTER_TOOL_SCHEMAS:
        return name
    if name.startswith("openrouter_"):
        return name.replace("_", ":", 1)
    if name == "openrouter":
        return "openrouter:web_search"
    return name


class BaseAgent(ABC):
    name: str
    display_name: str = ""
    description: str
    routing_criteria: str = ""
    model: str = MODEL_AGENT_DEFAULT
    model_simple: str | None = None
    vision_capable: bool = False
    timeout: int = MODEL_AGENT_TIMEOUT
    enabled: bool = True
    tools: list[str] = []
    system_prompt: str = ""

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

    @cached_property
    def _log(self):
        return get_logger(type(self).__module__)

    async def emit(self, ctx: AgentContext, key: str, **kwargs: str) -> None:
        """Emit a progress message. No-op when no reporter is attached (e.g. tests)."""
        if ctx.reporter is not None:
            await ctx.reporter.emit(key, **kwargs)

    def _model(self, ctx: AgentContext | None = None) -> str:
        if ctx is not None and ctx.model is not None:
            return ctx.model
        return self.model

    def _timeout(self) -> int:
        return int(self.timeout)

    def _format_memory(self, ctx: AgentContext) -> str:
        memory = ctx.memory
        if memory is None:
            return "(none)"
        facts = getattr(memory, "facts", []) or []
        lines = []
        for f in facts:
            predicate = getattr(f, "predicate", getattr(f, "key", "?"))
            value = f.value
            origin = _fact_origin(getattr(f, "provenance", None))
            conf = getattr(f, "confidence", None)
            conf_s = f"{float(conf):.2f}" if conf is not None else "?"
            recency = _format_fact_recency(getattr(f, "created_at", None))
            lines.append(
                f"- {predicate}: {value} ({origin}, confidence {conf_s}, {recency})"
            )
        return "\n".join(lines) if lines else "(none)"

    def _format_contacts(self, ctx: AgentContext) -> str:
        if ctx.contacts is None:
            return ""
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
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(ctx.timezone)
        except Exception:
            from datetime import timezone as _tz

            tz = _tz.utc
        now = datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z")
        datetime_line = f"Current date and time: {now}\n\n"

        identity_builder = ctx.identity_builder
        persona_block = ""
        biography_block = ""
        if identity_builder is not None:
            identity = identity_builder(
                ctx.persona,
                self._format_memory(ctx),
                profile=getattr(ctx.memory, "profile", None)
                if ctx.memory is not None
                else None,
                contacts_context=self._format_contacts(ctx),
            )
            persona_block, biography_block = _split_identity(identity)
        rendered = agent_instructions.format(**extra) if extra else agent_instructions
        if ctx.screen_context_note:
            rendered = f"{ctx.screen_context_note}\n\n{rendered}"
        if ctx.resume_recap:
            rendered = f"{ctx.resume_recap}\n\n{rendered}"
        if ctx.open_priorities_note:
            rendered = f"{ctx.open_priorities_note}\n\n{rendered}"
        skills_block = self._format_active_skills(ctx)
        if skills_block:
            rendered = f"{skills_block}\n\n{rendered}"
        procedure_block = getattr(ctx, "procedure_guidance", None)
        if procedure_block:
            rendered = f"{procedure_block}\n\n{rendered}"
        hint = getattr(ctx, "conductor_hint", None)
        if hint:
            lines = [
                "Routing hint (optional, not a DAG — scale effort; skip unused agents):"
            ]
            for item in hint:
                agent = item.get("agent", "")
                prompt = item.get("prompt", "")
                lines.append(f"- {agent}: {prompt}")
            rendered = "\n".join(lines) + "\n\n" + rendered
        sections = [datetime_line.rstrip(), MEMORY_CONSTITUTION.rstrip()]
        if persona_block:
            sections.append(persona_block.rstrip())
        sections.append(rendered.rstrip())
        if biography_block:
            sections.append(f"{BIOGRAPHY_HEADING}\n{biography_block.rstrip()}")
        return "\n\n".join(sections) + "\n"

    def _visible_tool_names(self, ctx: AgentContext, names: list[str]) -> list[str]:
        visible = list(names)
        skill_tool_names = getattr(ctx, "skill_tool_names", None)
        if skill_tool_names is not None:
            allowed = set(skill_tool_names)
            visible = [
                n for n in visible if n in allowed or n == _PROCEDURE_INVOKE_TOOL
            ]
        procedure_tool_names = getattr(ctx, "procedure_tool_names", None)
        if procedure_tool_names is not None:
            allowed = set(procedure_tool_names)
            visible = [n for n in visible if n in allowed]
        return visible

    def _format_active_skills(self, ctx: AgentContext) -> str:
        """Render each active skill's instructions (and any reference-file content,
        FR-022) as a system-prompt preamble block. No-op when no skills matched."""
        skills = getattr(ctx, "active_skills", None)
        if not skills:
            return ""
        blocks: list[str] = []
        for skill in skills:
            name = getattr(skill, "name", "")
            instructions = getattr(skill, "instructions", "")
            block = f"[Skill: {name}]\n{instructions}"
            for ref in getattr(skill, "reference_files", None) or []:
                filename = getattr(ref, "filename", "")
                content = getattr(ref, "content", "")
                block += f"\n\n[Reference: {filename}]\n{content}"
            blocks.append(block)
        return "\n\n".join(blocks)

    # ── Tool execution ────────────────────────────────────────────────────────

    async def call_tool(
        self,
        name: str,
        ctx: AgentContext,
        _iteration: int = -1,
        _lm_args: dict | None = None,
        _call_id: str | None = None,
        _approved_call_id: str | None = None,
        **kwargs: Any,
    ) -> ToolCall:
        """Execute a registered tool with capability enforcement and hook dispatch.

        READ tools execute in any gate state.
        An asks-first WRITE tool is parked, not run, unless the user approved this
        exact call (`_approved_call_id`) or a plan pre-approved the tool.
        """
        from ze_agents.tool import get_tool

        spec = get_tool(name)

        stored_args = _lm_args if _lm_args is not None else kwargs
        workspace_thread_id.set(ctx.session_id)

        if spec.access.value == "write" and ctx.retry_mode:
            log.info("tool_blocked_retry", tool=name, agent=self.name)
            return ToolCall(
                tool_name=name,
                args=stored_args,
                result=RETRY_WRITE_REFUSAL,
                duration_ms=0,
                success=False,
                error="blocked: retry runs cannot change anything",
                gate="denied",
            )

        hooks = get_hooks()
        confirmation_gate = "none"
        approval: dict[str, Any] | None = None
        if spec.access.value == "write":
            approved = _approved_call_id is not None or (
                _call_id is not None and _call_id in ctx.approved_call_ids
            )
            if approved:
                confirmation_gate = "approved"
                approval = {
                    "request_id": ctx.approval_request_id,
                    "outcome": "approved",
                }
            elif name in ctx.pre_approved_writes:
                confirmation_gate = "pre_approved"
                approval = {"outcome": "pre_approved"}
            else:
                resolution = await self._resolve_ask(spec, ctx, dict(kwargs), hooks)
                if resolution is not None:
                    if resolution.refuse is not None:
                        return _refusal(
                            name,
                            stored_args,
                            resolution.refuse,
                            result=resolution.result,
                        )
                    if ctx.write_round >= MAX_WRITE_ROUNDS:
                        return _refusal(
                            name,
                            stored_args,
                            OVER_CAP_RESULT,
                            gate="refused_over_cap",
                        )
                    if not ctx.loop_active:
                        raise AgentConfigError(
                            f"asks-first tool {name!r} called outside the agent loop"
                        )
                    summary = _summarize(spec, stored_args)
                    if resolution.reason == "check" and resolution.text:
                        summary = resolution.text
                    return ToolCall(
                        tool_name=name,
                        args=stored_args,
                        result=None,
                        duration_ms=0,
                        success=False,
                        error="parked: awaiting the user's approval",
                        gate="parked",
                        parked=ParkedWrite(
                            item_id=str(uuid4()),
                            call_id=_call_id or "",
                            tool=name,
                            args=dict(stored_args),
                            effect_phrase=spec.effect_phrase or name,
                            summary=summary,
                            agent=self.name,
                            editable_field=spec.editable_field,
                            conflict=resolution.text
                            if resolution.reason == "constraint"
                            else None,
                            reason=resolution.reason,
                        ),
                    )

        # ── Hook: before ─────────────────────────────────────────────────────
        args: dict[str, Any] = dict(kwargs)
        for hook in hooks:
            try:
                modified = await hook.on_tool_start(
                    ToolStartEvent(name, args, ctx, _iteration)
                )
                if modified is not None:
                    args = modified
            except HookAbort as e:
                log.info(
                    "tool_skipped_by_hook", tool=name, agent=self.name, reason=e.reason
                )
                return ToolCall(
                    tool_name=name,
                    args=stored_args,
                    result=e.result,
                    duration_ms=0,
                    success=False,
                    error=f"skipped: {e.reason}",
                )
            except Exception as exc:
                log.warning(
                    "hook_error_on_tool_start",
                    tool=name,
                    agent=self.name,
                    error=str(exc),
                )

        # ── Execute ───────────────────────────────────────────────────────────
        log.debug("tool_start", tool=name, agent=self.name, access=spec.access.value)
        start = time.monotonic()
        approval_token = current_approval.set(approval)
        try:
            result = await spec.func(**args)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            log.warning("tool_error", tool=name, agent=self.name, error=str(exc))
            tool_call = ToolCall(
                tool_name=name,
                args=stored_args,
                result=None,
                duration_ms=duration_ms,
                success=False,
                error=str(exc),
            )
            await _dispatch_tool_end(hooks, name, tool_call, ctx, _iteration)
            return tool_call
        finally:
            current_approval.reset(approval_token)

        duration_ms = int((time.monotonic() - start) * 1000)
        log.info("tool_complete", tool=name, agent=self.name, duration_ms=duration_ms)
        tool_call = ToolCall(
            tool_name=name,
            args=stored_args,
            result=result,
            duration_ms=duration_ms,
            success=True,
            gate=confirmation_gate,
            approval=approval,
        )

        # ── Hook: after ───────────────────────────────────────────────────────
        await _dispatch_tool_end(hooks, name, tool_call, ctx, _iteration)
        return tool_call

    async def _apply_resume(
        self,
        ctx: AgentContext,
        resume: ParkedLoop,
        messages: list[dict],
        accumulated: list[ToolCall],
        deps: dict[str, Any],
    ) -> None:
        """Answer a parked response: run exactly the approved calls, then the child.

        No model call happens here. A child delegate that parks again re-parks this
        loop (`LoopParked`) with the new child.
        """
        from ze_agents.delegate import run_delegate

        for pw in resume.parked:
            decision = ctx.write_decisions.get(pw.item_id)
            approved = decision is not None and decision.outcome in (
                "approved",
                "edited",
            )
            if approved:
                args = dict(pw.args)
                if (
                    decision.outcome == "edited"
                    and pw.editable_field
                    and decision.edited_text is not None
                ):
                    args[pw.editable_field] = decision.edited_text
                merged = _merge_deps(pw.tool, args, {**deps, "ctx": ctx})
                tool_call = await self.call_tool(
                    pw.tool,
                    ctx,
                    _iteration=resume.iteration,
                    _lm_args=args,
                    _approved_call_id=pw.call_id,
                    **merged,
                )
            else:
                tool_call = ToolCall(
                    tool_name=pw.tool,
                    args=pw.args,
                    result=DECLINED_RESULT,
                    duration_ms=0,
                    success=False,
                    error="denied by user",
                    gate="denied",
                )
            accumulated.append(tool_call)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": pw.call_id,
                    "content": DECLINED_RESULT
                    if not approved
                    else _serialise_result(tool_call),
                }
            )

        if resume.child is None:
            return
        tool_call = await run_delegate(
            resume.child_arguments or {},
            ctx,
            resume.iteration,
            caller_name=self.name,
            resume=resume.child,
        )
        if tool_call.child_loop is not None:
            raise LoopParked(
                ParkedLoop(
                    agent=self.name,
                    messages=list(messages),
                    accumulated=list(accumulated),
                    iteration=resume.iteration,
                    parked=[],
                    child=tool_call.child_loop,
                    child_call_id=resume.child_call_id,
                    child_arguments=resume.child_arguments,
                )
            )
        accumulated.append(tool_call)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": resume.child_call_id,
                "content": _serialise_result(tool_call),
            }
        )

    async def _resolve_ask(
        self, spec: Any, ctx: AgentContext, args: dict[str, Any], hooks: list
    ) -> _AskResolution | None:
        """Steps 4-6 of the resolution order: None means the call may run."""
        if spec.access.value != "write":
            return None
        if spec.constraint_gate:
            for hook in hooks:
                check = getattr(hook, "check_call", None)
                if check is None:
                    continue
                decision = await check(ToolStartEvent(spec.name, args, ctx, -1))
                if decision.kind == "refuse":
                    return _AskResolution(
                        refuse=decision.message, result=decision.result
                    )
                if decision.kind == "ask":
                    return _AskResolution(text=decision.reason, reason="constraint")
        if spec.ask_check is not None:
            decision = spec.ask_check(args, ctx)
            if decision.kind == "refuse":
                return _AskResolution(refuse=decision.message)
            if decision.kind == "ask":
                return _AskResolution(text=decision.reason, reason="check")
            return None
        if spec.asks_first:
            return _AskResolution(reason="asks_first")
        return None

    # ── Agentic loop ──────────────────────────────────────────────────────────

    async def agentic_loop(
        self,
        ctx: AgentContext,
        client: LLMClient,
        messages: list[dict],
        system: str,
        deps: dict[str, Any] | None = None,
        tool_names: list[str] | None = None,
        max_iterations: int = 6,
        max_history_tokens: int | None = None,
        max_tokens: int = 2000,
    ) -> tuple[str, list[ToolCall]]:
        """Drive a ReAct loop: LLM picks tools, ze dispatches them, repeat until text.

        Raises `LoopParked` after a response whose asks-first calls were parked.
        """
        previous_active = ctx.loop_active
        ctx.loop_active = True
        try:
            return await self._run_loop(
                ctx,
                client,
                messages,
                system,
                deps,
                tool_names,
                max_iterations,
                max_history_tokens,
                max_tokens,
            )
        finally:
            ctx.loop_active = previous_active

    async def _run_loop(
        self,
        ctx: AgentContext,
        client: LLMClient,
        messages: list[dict],
        system: str,
        deps: dict[str, Any] | None,
        tool_names: list[str] | None,
        max_iterations: int,
        max_history_tokens: int | None,
        max_tokens: int,
    ) -> tuple[str, list[ToolCall]]:
        from ze_agents.delegate import (
            DELEGATE_TOOL_NAME,
            DELEGATE_TOOL_SCHEMA,
            run_delegate,
        )
        from ze_agents.tool import get_tool

        names = tool_names if tool_names is not None else list(self.tools)
        from ze_agents.tool import registered_tools

        registered = registered_tools()
        if not getattr(self, "workspace_opt_out", False):
            for platform_name in _PLATFORM_TOOLS:
                if platform_name in registered and platform_name not in names:
                    names.append(platform_name)
        if _PROCEDURE_INVOKE_TOOL in registered and _PROCEDURE_INVOKE_TOOL not in names:
            names.append(_PROCEDURE_INVOKE_TOOL)
        accumulated: list[ToolCall] = []
        _deps = deps or {}
        hooks = get_hooks()

        await _dispatch_loop_hooks(
            hooks, "on_loop_start", LoopStartEvent(self.name, ctx)
        )

        # Fetch tool-executor memory context for direct invocations (e.g. from GoalExecutor)
        # that bypass the fetch_context graph node. Prepend as a context block to system.
        tool_ctx_block = await _fetch_tool_executor_context(ctx)
        if tool_ctx_block:
            system = f"{system}\n\n{tool_ctx_block}"

        def _collect_sources(found: list[Source]) -> None:
            add_sources(ctx.sources, found)

        start_iteration = 0
        resume = ctx.resume
        if resume is not None and resume.agent == self.name:
            ctx.resume = None
            messages[:] = list(resume.messages)
            accumulated.extend(resume.accumulated)
            await self._apply_resume(ctx, resume, messages, accumulated, _deps)
            start_iteration = resume.iteration + 1

        for iteration in range(start_iteration, max_iterations):
            if ctx.abort_token is not None and ctx.abort_token.is_set:
                raise AgentAbortedError(ctx.abort_token.reason)

            visible = self._visible_tool_names(ctx, names)
            tool_schemas = [
                _OPENROUTER_TOOL_SCHEMAS[n]
                if n in _OPENROUTER_TOOL_SCHEMAS
                else DELEGATE_TOOL_SCHEMA
                if n == DELEGATE_TOOL_NAME
                else get_tool(n).llm_schema()
                for n in visible
            ]

            if max_history_tokens is not None:
                _truncate_messages(messages, max_history_tokens)

            _token_sink = getattr(ctx, "token_sink", None)
            if _token_sink is not None and hasattr(
                client, "stream_complete_with_tools"
            ):
                text, tool_calls = await client.stream_complete_with_tools(
                    messages=messages,
                    model=ctx.model or self.model,
                    tools=tool_schemas,
                    system=system,
                    max_tokens=max_tokens,
                    token_sink=_token_sink,
                    source_sink=_collect_sources,
                )
            else:
                text, tool_calls = await client.complete_with_tools(
                    messages=messages,
                    model=ctx.model or self.model,
                    tools=tool_schemas,
                    system=system,
                    max_tokens=max_tokens,
                    source_sink=_collect_sources,
                )

            if text:
                log.debug(
                    "agentic_loop_done",
                    agent=self.name,
                    iterations=iteration + 1,
                    tool_calls=len(accumulated),
                )
                await _dispatch_loop_hooks(
                    hooks,
                    "on_loop_end",
                    LoopEndEvent(
                        self.name, ctx, accumulated, iterations_used=iteration + 1
                    ),
                )
                return text, accumulated

            if tool_calls is None:
                raise AgentError(
                    f"complete_with_tools returned no text and no tool calls "
                    f"(iteration {iteration + 1})"
                )

            messages.append(
                {
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
                }
            )

            invoke_calls = [
                tc for tc in tool_calls if tc["name"] == _PROCEDURE_INVOKE_TOOL
            ]
            if invoke_calls and getattr(ctx, "procedure_invocation_id", None) is None:
                tool_calls = invoke_calls[:1]

            parked_writes: list[ParkedWrite] = []
            child: ParkedLoop | None = None
            child_call_id: str | None = None
            child_arguments: dict[str, Any] | None = None

            for tc in tool_calls:
                if _is_openrouter_server_tool(tc["name"]):
                    canonical = _canonical_openrouter_tool_name(tc["name"])
                    tool_call = ToolCall(
                        tool_name=canonical,
                        args=tc["arguments"],
                        result="[handled by OpenRouter]",
                        duration_ms=0,
                        success=True,
                    )
                    accumulated.append(tool_call)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": "[search complete]",
                        }
                    )
                elif tc["name"] == DELEGATE_TOOL_NAME:
                    if child is not None:
                        tool_call = ToolCall(
                            tool_name=DELEGATE_TOOL_NAME,
                            args=tc["arguments"],
                            result=_DEFERRED_DELEGATE_RESULT,
                            duration_ms=0,
                            success=True,
                        )
                    else:
                        tool_call = await run_delegate(
                            tc["arguments"],
                            ctx,
                            iteration,
                            caller_name=self.name,
                        )
                        if tool_call.child_loop is not None:
                            child = tool_call.child_loop
                            child_call_id = tc["id"]
                            child_arguments = dict(tc["arguments"])
                            continue
                    accumulated.append(tool_call)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": _serialise_result(tool_call),
                        }
                    )
                else:
                    merged = _merge_deps(
                        tc["name"], tc["arguments"], {**_deps, "ctx": ctx}
                    )
                    tool_call = await self.call_tool(
                        tc["name"],
                        ctx,
                        _iteration=iteration,
                        _lm_args=tc["arguments"],
                        _call_id=tc["id"],
                        **merged,
                    )
                    if tool_call.parked is not None:
                        parked_writes.append(tool_call.parked)
                        continue
                    accumulated.append(tool_call)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": _serialise_result(tool_call),
                        }
                    )

            if parked_writes or child is not None:
                raise LoopParked(
                    ParkedLoop(
                        agent=self.name,
                        messages=list(messages),
                        accumulated=list(accumulated),
                        iteration=iteration,
                        parked=parked_writes,
                        child=child,
                        child_call_id=child_call_id,
                        child_arguments=child_arguments,
                    )
                )

        log.warning(
            "agentic_loop_max_iterations",
            agent=self.name,
            max_iterations=max_iterations,
        )
        await _dispatch_loop_hooks(
            hooks,
            "on_loop_end",
            LoopEndEvent(self.name, ctx, accumulated, iterations_used=max_iterations),
        )
        text = await client.complete(
            messages=messages,
            model=ctx.model or self.model,
            system=system,
            max_tokens=max_tokens,
        )
        return text, accumulated


# ── Module-level helpers ──────────────────────────────────────────────────────


@dataclass
class _AskResolution:
    refuse: str | None = None
    result: Any = None
    text: str = ""
    reason: ParkReason = "asks_first"


def _refusal(
    name: str,
    args: dict[str, Any],
    message: str,
    *,
    gate: str = "denied",
    result: Any = None,
) -> ToolCall:
    return ToolCall(
        tool_name=name,
        args=args,
        result=message if result is None else result,
        duration_ms=0,
        success=False,
        error=f"refused: {message}",
        gate=gate,
    )


def _summarize(spec: Any, args: dict[str, Any]) -> str:
    if spec.summarize is not None:
        try:
            return str(spec.summarize(args))
        except Exception as exc:
            log.warning("tool_summarize_failed", tool=spec.name, error=str(exc))
    return generic_summary(args)


async def _dispatch_loop_hooks(hooks: list, method: str, event: Any) -> None:
    """Dispatch a loop lifecycle hook to all registered hooks."""
    for hook in hooks:
        try:
            await getattr(hook, method)(event)
        except AgentAbortedError:
            raise
        except Exception as exc:
            log.warning("hook_error", hook_method=method, error=str(exc))


async def _dispatch_tool_end(
    hooks: list,
    name: str,
    tool_call: ToolCall,
    ctx: AgentContext,
    iteration: int,
) -> None:
    for hook in hooks:
        try:
            await hook.on_tool_end(ToolEndEvent(name, tool_call, ctx, iteration))
        except Exception as exc:
            log.warning("hook_error_on_tool_end", tool=name, error=str(exc))


def _merge_deps(tool_name: str, llm_args: dict, deps: dict[str, Any]) -> dict:
    """Inject internal deps into tool kwargs for params the LLM cannot provide."""
    import inspect
    from ze_agents.tool import get_tool

    if _is_openrouter_server_tool(tool_name):
        return dict(llm_args)

    spec = get_tool(tool_name)
    merged = dict(llm_args)
    for param_name in inspect.signature(spec.func).parameters:
        if param_name not in merged and param_name in deps:
            merged[param_name] = deps[param_name]
    return merged


def _serialise_result(tc: ToolCall) -> str:
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


async def _fetch_tool_executor_context(ctx: Any) -> str:
    """Fetch facts + task state via ToolExecutorPolicy for direct agent invocations.

    Only runs when ctx.memory_store is set (goal executor path). Returns a formatted
    context block for prepending to the system prompt, or empty string if nothing
    is available.
    """
    store = getattr(ctx, "memory_store", None)
    if store is None:
        return ""
    try:
        from uuid import UUID

        goal_id_str = ctx.extensions.get("goal_id") if ctx.extensions else None
        goal_id = UUID(goal_id_str) if goal_id_str else None

        # Use ctx.embed_fn if available (injected by container); fall back to None
        # so the retrieve call still works with stores that accept no embedding.
        embed_fn = getattr(ctx, "embed_fn", None)
        embedding = embed_fn(ctx.prompt) if embed_fn is not None else None

        request = RetrievalRequest(
            module="tool_executor",
            agent="tool_executor",
            query_text=ctx.prompt,
            query_embedding=embedding,
            task_id=None,
            goal_id=goal_id,
            max_tokens=800,
        )
        memory_ctx = await store.retrieve(request)
    except Exception as exc:
        log.warning("tool_executor_context_fetch_failed", error=str(exc))
        return ""

    lines: list[str] = []
    facts = getattr(memory_ctx, "facts", [])
    if facts:
        lines.append("## Relevant facts")
        lines.extend(f"- {f.predicate}: {f.value}" for f in facts)
    task_state = getattr(memory_ctx, "task_state", None)
    if task_state is not None:
        lines.append("## Current task state")
        lines.append(f"Status: {task_state.status}")
        if task_state.open_steps:
            lines.append("Open steps: " + ", ".join(task_state.open_steps))
        if task_state.blocked_by:
            lines.append("Blocked by: " + ", ".join(task_state.blocked_by))
        if task_state.next_action:
            lines.append(f"Next action: {task_state.next_action}")
    return "\n".join(lines)


def _truncate_messages(messages: list[dict], max_tokens: int) -> None:
    """Remove oldest tool-call rounds until token estimate is under budget.

    O(n²) — re-serializes all messages on every eviction pass. Acceptable at
    current agentic-loop depths (typically <30 messages); revisit if history
    grows into the hundreds.
    """
    while True:
        total = sum(len(json.dumps(m)) // 4 for m in messages)
        if total <= max_tokens:
            break

        protected_from = max(0, len(messages) - 4)

        round_start = None
        for i in range(protected_from):
            if messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
                round_start = i
                break

        if round_start is None:
            break

        tool_call_ids = {tc["id"] for tc in messages[round_start]["tool_calls"]}
        indices_to_remove = [round_start]
        for j in range(round_start + 1, len(messages)):
            if (
                messages[j].get("role") == "tool"
                and messages[j].get("tool_call_id") in tool_call_ids
            ):
                indices_to_remove.append(j)
            elif messages[j].get("role") != "tool":
                break

        for idx in sorted(indices_to_remove, reverse=True):
            messages.pop(idx)
