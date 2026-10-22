from __future__ import annotations

import asyncio
import base64
import json
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from ze_agents.effects import effect_imperative
from ze_agents.budget import has_budget, partial_answer
from ze_agents.errors import AgentTimeoutError, LoopParked, UnknownAgentError
from ze_agents.park import (
    ConfirmItem,
    ParkedSubtask,
    WriteConfirmation,
    WriteDecision,
)
from ze_logging import get_logger
from ze_agents.registry import get_agent, get_agent_class
from ze_core.orchestration.state import AgentState
from ze_agents.types import AgentContext, AgentResult, add_sources

log = get_logger(__name__)


def _conductor_kwargs(base_ctx: AgentContext) -> dict[str, Any]:
    counts = getattr(base_ctx, "conductor_delegate_counts", None)
    if counts is None:
        base_ctx.conductor_delegate_counts = counts = {}
    return {
        "conductor_hint": getattr(base_ctx, "conductor_hint", None),
        "conductor_ledger": getattr(base_ctx, "conductor_ledger", None) or [],
        "conductor_delegate_counts": counts,
        "conductor_delegate_total": int(
            getattr(base_ctx, "conductor_delegate_total", 0) or 0
        ),
    }


def _prompt_note_kwargs(base_ctx: AgentContext) -> dict[str, Any]:
    return {
        "screen_context_note": base_ctx.screen_context_note,
        "preset_note": base_ctx.preset_note,
        "resume_recap": base_ctx.resume_recap,
        "open_priorities_note": base_ctx.open_priorities_note,
        "preset": base_ctx.preset,
    }


def _procedure_kwargs(base_ctx: AgentContext) -> dict[str, Any]:
    return {
        "procedure_guidance": getattr(base_ctx, "procedure_guidance", None),
        "procedure_matches": getattr(base_ctx, "procedure_matches", None),
        "procedure_tool_names": getattr(base_ctx, "procedure_tool_names", None),
        "procedure_invocation_id": getattr(base_ctx, "procedure_invocation_id", None),
        "procedure_invoked_id": getattr(base_ctx, "procedure_invoked_id", None),
        "procedure_invoked_version_id": getattr(
            base_ctx, "procedure_invoked_version_id", None
        ),
    }


BUDGET_DENIED_REPLY = (
    "Okay, I didn't run that: it would have gone over your spend limit."
)


def _agent_enabled(agent_name: str) -> bool:
    try:
        return bool(getattr(get_agent_class(agent_name), "enabled", True))
    except UnknownAgentError:
        log.warning("preflight_unknown_agent", agent=agent_name)
        return True


def _answer(resume: Any) -> tuple[str, dict[str, str]]:
    """Read a graph resume value: `{"choice", "edits"}` or a bare choice string."""
    if isinstance(resume, dict):
        edits = resume.get("edits") or {}
        return str(resume.get("choice") or "deny"), dict(edits)
    if isinstance(resume, str):
        return resume, {}
    return "deny", {}


async def preflight(state: AgentState, config: RunnableConfig) -> dict:
    """Block disabled agents and open the spend-budget pause when over budget."""
    envelope = state.get("envelope")
    subtasks = envelope.subtasks if envelope and envelope.subtasks else []
    if not subtasks or not any(_agent_enabled(st.agent) for st in subtasks):
        return {"blocked": True}

    if config["configurable"].get("retry_mode") or state.get("budget_approved"):
        return {}
    checker = config["configurable"].get("budget_checker")
    if checker is None:
        return {}
    status = await checker.check(session_id=state["session_id"])
    if status.within_budget:
        return {}
    summary = f"${status.current_spend_usd:.2f} of ${status.limit_usd:.2f}"
    return {
        "budget_status": {
            "scope": status.scope,
            "current_spend_usd": status.current_spend_usd,
            "limit_usd": status.limit_usd,
        },
        "write_confirmation": WriteConfirmation(
            request_id=str(uuid4()),
            kind="budget",
            round=1,
            items=[
                ConfirmItem(
                    item_id="budget",
                    agent="",
                    tool=None,
                    effect_phrase=f"continue past your {status.scope} spend limit",
                    summary=summary,
                )
            ],
        ),
    }


async def await_budget_confirmation(state: AgentState, config: RunnableConfig) -> dict:
    resume = interrupt(state["write_confirmation"])
    confirmation: WriteConfirmation = state["write_confirmation"]
    choice, _ = _answer(resume)
    if choice == "approve":
        return {"budget_approved": True, "write_confirmation": None}
    outcome = "timed_out" if choice == "timeout" else "denied"
    return {
        "write_confirmation": None,
        "final_response": BUDGET_DENIED_REPLY,
        "write_outcomes": list(state.get("write_outcomes") or [])
        + [
            {
                "request_id": confirmation.request_id,
                "round": confirmation.round,
                "item_id": item.item_id,
                "agent": item.agent,
                "tool": None,
                "summary": item.summary,
                "outcome": outcome,
            }
            for item in confirmation.items
        ],
    }


async def await_write_confirmation(state: AgentState, config: RunnableConfig) -> dict:
    resume = interrupt(state["write_confirmation"])
    confirmation: WriteConfirmation = state["write_confirmation"]
    choice, edits = _answer(resume)
    decisions: list[WriteDecision] = []
    for item in confirmation.items:
        if choice == "approve":
            text = edits.get(item.item_id)
            if text is not None and item.editable_field:
                decisions.append(WriteDecision(item.item_id, "edited", str(text)))
            else:
                decisions.append(WriteDecision(item.item_id, "approved"))
        elif choice == "timeout":
            decisions.append(WriteDecision(item.item_id, "timed_out"))
        else:
            decisions.append(WriteDecision(item.item_id, "denied"))
    shown = {d.item_id: d for d in decisions}
    for alias, item_id in confirmation.aliases.items():
        answer = shown[item_id]
        approved = answer.outcome in ("approved", "edited")
        decisions.append(
            WriteDecision(alias, "duplicate" if approved else answer.outcome)
        )
    log.info(
        "orchestration_write_confirmation_answered",
        session_id=state["session_id"],
        round=confirmation.round,
        choice=choice,
    )
    return {
        "write_decisions": decisions,
        "write_rounds": int(state.get("write_rounds") or 0) + 1,
    }


def _build_confirmation(parked: list[ParkedSubtask], round_: int) -> WriteConfirmation:
    """One item per distinct (tool, args); a repeat of a shown call becomes an alias."""
    items: list[ConfirmItem] = []
    aliases: dict[str, str] = {}
    seen: dict[tuple[str, str], str] = {}
    for ps in sorted(parked, key=lambda p: p.index):
        for pw in ps.loop.all_parked():
            key = (pw.tool, json.dumps(pw.args, sort_keys=True, default=str))
            if key in seen:
                aliases[pw.item_id] = seen[key]
                continue
            seen[key] = pw.item_id
            items.append(
                ConfirmItem(
                    item_id=pw.item_id,
                    agent=pw.agent,
                    tool=pw.tool,
                    effect_phrase=effect_imperative(pw.effect_phrase),
                    summary=pw.summary,
                    editable_field=pw.editable_field,
                    proposed_text=(
                        str(pw.args.get(pw.editable_field))
                        if pw.editable_field
                        and pw.args.get(pw.editable_field) is not None
                        else None
                    ),
                    conflict=pw.conflict,
                )
            )
    return WriteConfirmation(
        request_id=str(uuid4()),
        kind="write",
        round=round_,
        items=items,
        aliases=aliases,
    )


def _outcome_rows(
    confirmation: WriteConfirmation, decisions: dict[str, WriteDecision]
) -> list[dict]:
    rows = []
    for item in confirmation.items:
        decision = decisions.get(item.item_id)
        rows.append(
            {
                "request_id": confirmation.request_id,
                "round": confirmation.round,
                "item_id": item.item_id,
                "agent": item.agent,
                "tool": item.tool,
                "effect": item.effect_phrase,
                "summary": item.summary,
                "outcome": decision.outcome if decision else "superseded",
            }
        )
    return rows


def _park_updates(state: dict, new_parked: list[ParkedSubtask]) -> dict:
    """State updates after an execution pass: record the answered round, open the next."""
    outcomes = list(state.get("write_outcomes") or [])
    answered = state.get("write_confirmation")
    decisions = {d.item_id: d for d in state.get("write_decisions") or []}
    if answered is not None and decisions:
        outcomes.extend(_outcome_rows(answered, decisions))
    updates: dict[str, Any] = {
        "write_outcomes": outcomes,
        "write_decisions": [],
        "write_confirmation": None,
        "parked_subtasks": [],
    }
    if new_parked:
        rounds = int(state.get("write_rounds") or 0)
        updates["parked_subtasks"] = new_parked
        updates["write_confirmation"] = _build_confirmation(new_parked, rounds + 1)
    return updates


def _pre_approved(
    base_ctx: AgentContext, config: RunnableConfig, state: dict
) -> frozenset[str]:
    extra = config["configurable"].get("pre_approved_writes") or ()
    step = state.get("pre_approved_writes") or ()
    return frozenset(base_ctx.pre_approved_writes) | frozenset(extra) | frozenset(step)


def _resume_kwargs(state: dict, index: int) -> dict[str, Any]:
    """AgentContext fields that re-enter subtask `index`'s parked loop, if it parked."""
    parked = {ps.index: ps for ps in state.get("parked_subtasks") or []}
    decisions = {d.item_id: d for d in state.get("write_decisions") or []}
    confirmation = state.get("write_confirmation")
    kwargs: dict[str, Any] = {"write_round": int(state.get("write_rounds") or 0)}
    if index in parked and decisions:
        kwargs["resume"] = parked[index].loop
        kwargs["write_decisions"] = decisions
        kwargs["approval_request_id"] = (
            confirmation.request_id if confirmation is not None else None
        )
    return kwargs


async def execute_tool(state: AgentState, config: RunnableConfig) -> dict:
    envelope = state.get("envelope")
    base_ctx = state.get("agent_context")

    if not envelope or not base_ctx:
        return {"error": "Missing routing envelope or agent context"}

    reporter = config["configurable"].get("reporter")
    token_queue: asyncio.Queue | None = config["configurable"].get("token_queue")
    token_sink = config["configurable"].get("token_sink")
    identity_builder = config["configurable"].get("identity_builder")
    abort_token = config["configurable"].get("abort_token")
    component_hook = config["configurable"].get("component_hook")
    embed_fn = _embed_fn(config)

    if envelope.is_compound:
        return await _execute_compound(
            envelope.subtasks,
            base_ctx,
            state,
            config,
            reporter=reporter,
            identity_builder=identity_builder,
            abort_token=abort_token,
            component_hook=component_hook,
            embed_fn=embed_fn,
        )
    return await _execute_single(
        envelope.subtasks[0],
        base_ctx,
        state,
        config,
        token_queue=token_queue,
        token_sink=token_sink,
        reporter=reporter,
        identity_builder=identity_builder,
        abort_token=abort_token,
        component_hook=component_hook,
        embed_fn=embed_fn,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _embed_fn(config: RunnableConfig) -> Any:
    embedder = config["configurable"].get("embedder")
    if embedder is None:
        return None
    return embedder.encode_query


def _build_messages(state: dict, agent_name: str, base_ctx: AgentContext) -> list[dict]:
    if state.get("image_data"):
        return [_build_image_message(state)]
    return base_ctx.messages


def _build_image_message(state: dict) -> dict:
    prompt = state.get("prompt") or state.get("image_caption") or ""
    mime = state.get("image_mime", "image/jpeg")
    content: list = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime};base64,{base64.b64encode(state['image_data']).decode()}",
                "detail": "auto",
            },
        }
    ]
    if prompt:
        content.append({"type": "text", "text": prompt})
    return {"role": "user", "content": content}


def _sync_procedure_invocation(source: AgentContext, dest: AgentContext) -> None:
    dest.procedure_invocation_id = getattr(source, "procedure_invocation_id", None)
    dest.procedure_invoked_id = getattr(source, "procedure_invoked_id", None)
    dest.procedure_invoked_version_id = getattr(
        source, "procedure_invoked_version_id", None
    )
    dest.procedure_tool_names = getattr(source, "procedure_tool_names", None)


async def _execute_single(
    subtask: Any,
    base_ctx: AgentContext,
    state: dict,
    config: RunnableConfig,
    token_queue: asyncio.Queue | None = None,
    token_sink: Any = None,
    reporter: Any = None,
    identity_builder: Any = None,
    abort_token: Any = None,
    component_hook: Any = None,
    embed_fn: Any = None,
) -> dict:
    ctx = AgentContext(
        session_id=base_ctx.session_id,
        prompt=subtask.prompt,
        memory=base_ctx.memory,
        contacts=base_ctx.contacts,
        persona=base_ctx.persona,
        timezone=base_ctx.timezone,
        retry_mode=base_ctx.retry_mode,
        model=subtask.model or None,
        messages=_build_messages(state, subtask.agent, base_ctx),
        reporter=reporter,
        identity_builder=identity_builder,
        abort_token=abort_token,
        embed_fn=embed_fn,
        token_sink=token_sink,
        tool_sink=config["configurable"].get("tool_sink"),
        script_runner=config["configurable"].get("script_runner"),
        active_skills=base_ctx.active_skills,
        skill_tool_names=base_ctx.skill_tool_names,
        pre_approved_writes=_pre_approved(base_ctx, config, state),
        **_resume_kwargs(state, 0),
        **_prompt_note_kwargs(base_ctx),
        **_procedure_kwargs(base_ctx),
        **_conductor_kwargs(base_ctx),
    )
    result = await _run_with_timeout(
        subtask.agent, ctx, token_queue=token_queue, index=0
    )
    if isinstance(result, ParkedSubtask):
        return {
            **_park_updates(state, [result]),
            "agent_context": base_ctx,
            "conductor_ledger": list(getattr(ctx, "conductor_ledger", None) or []),
            "conductor_delegate_counts": dict(
                getattr(ctx, "conductor_delegate_counts", None) or {}
            ),
            "conductor_delegate_total": int(
                getattr(ctx, "conductor_delegate_total", 0) or 0
            ),
        }
    from ze_core.orchestration.procedure_activation import record_guided_actions

    await record_guided_actions(ctx, result, config)
    _sync_procedure_invocation(ctx, base_ctx)
    if getattr(ctx, "conductor_ledger", None) is not None:
        base_ctx.conductor_ledger = ctx.conductor_ledger
    if getattr(ctx, "conductor_delegate_counts", None) is not None:
        base_ctx.conductor_delegate_counts = ctx.conductor_delegate_counts
    base_ctx.conductor_delegate_total = int(
        getattr(ctx, "conductor_delegate_total", 0) or 0
    )
    components: list = list(state.get("preset_components") or [])
    if component_hook is not None:
        components += component_hook.pop_components(ctx.session_id)
    return {
        **_park_updates(state, []),
        "agent_result": result,
        "subtask_results": [],
        "components": components,
        "agent_context": base_ctx,
        "conductor_ledger": list(getattr(ctx, "conductor_ledger", None) or []),
        "conductor_delegate_counts": dict(
            getattr(ctx, "conductor_delegate_counts", None) or {}
        ),
        "conductor_delegate_total": int(
            getattr(ctx, "conductor_delegate_total", 0) or 0
        ),
    }


async def _execute_compound(
    subtasks: list,
    base_ctx: AgentContext,
    state: dict,
    config: RunnableConfig,
    reporter: Any = None,
    identity_builder: Any = None,
    abort_token: Any = None,
    component_hook: Any = None,
    embed_fn: Any = None,
    token_queue: asyncio.Queue | None = None,
    token_sink: Any = None,
) -> dict:
    if len(subtasks) == 1:
        return await _execute_single(
            subtasks[0],
            base_ctx,
            state,
            config,
            token_queue=token_queue,
            token_sink=token_sink,
            reporter=reporter,
            identity_builder=identity_builder,
            abort_token=abort_token,
            component_hook=component_hook,
            embed_fn=embed_fn,
        )

    completed_indexes = [int(i) for i in (state.get("completed_subtask_indexes") or [])]
    completed_set = set(completed_indexes)
    existing_results = list(state.get("subtask_results") or [])
    results_by_index: dict[int, AgentResult] = {}
    for idx, result in zip(completed_indexes, existing_results):
        results_by_index[idx] = result

    def _make_ctx(index: int, subtask: Any) -> AgentContext:
        ctx = AgentContext(
            session_id=base_ctx.session_id,
            prompt=subtask.prompt,
            memory=base_ctx.memory,
            contacts=base_ctx.contacts,
            persona=base_ctx.persona,
            timezone=base_ctx.timezone,
            retry_mode=base_ctx.retry_mode,
            model=subtask.model or None,
            messages=_build_messages(state, subtask.agent, base_ctx),
            reporter=reporter,
            identity_builder=identity_builder,
            abort_token=abort_token,
            embed_fn=embed_fn,
            tool_sink=config["configurable"].get("tool_sink"),
        script_runner=config["configurable"].get("script_runner"),
            active_skills=base_ctx.active_skills,
            skill_tool_names=base_ctx.skill_tool_names,
            pre_approved_writes=_pre_approved(base_ctx, config, state),
            **_resume_kwargs(state, index),
            **_prompt_note_kwargs(base_ctx),
            **_procedure_kwargs(base_ctx),
            **_conductor_kwargs(base_ctx),
        )
        return ctx

    to_run = [
        (i, st)
        for i, st in enumerate(subtasks)
        if i not in completed_set and _agent_enabled(st.agent)
    ]
    new_parked: list[ParkedSubtask] = []
    if to_run:
        ran = await asyncio.gather(
            *[
                _run_with_timeout(st.agent, _make_ctx(i, st), index=i)
                for i, st in to_run
            ]
        )
        for (i, _), outcome in zip(to_run, ran):
            if isinstance(outcome, ParkedSubtask):
                new_parked.append(outcome)
            else:
                results_by_index[i] = outcome

    ordered_indexes = sorted(results_by_index)
    return {
        **_park_updates(state, new_parked),
        "agent_result": None,
        "subtask_results": [results_by_index[i] for i in ordered_indexes],
        "completed_subtask_indexes": ordered_indexes,
        "components": list(state.get("preset_components") or []),
        "agent_context": base_ctx,
    }


async def _run_with_timeout(
    agent_name: str,
    ctx: AgentContext,
    token_queue: asyncio.Queue | None = None,
    index: int = 0,
) -> AgentResult | ParkedSubtask:
    """Run one agent. A loop that parked asks-first writes comes back as a
    `ParkedSubtask`; nothing here ever pauses the graph."""
    try:
        return await _run_agent(agent_name, ctx, token_queue)
    except LoopParked as parked:
        log.info("orchestration_subtask_parked", agent=agent_name, index=index)
        return ParkedSubtask(index=index, loop=parked.loop)


async def _run_agent(
    agent_name: str,
    ctx: AgentContext,
    token_queue: asyncio.Queue | None = None,
) -> AgentResult:
    """Run one agent.

    `tool_interrupts=False` is for subtasks that run inside `asyncio.gather`: a
    tool-level confirmation must not interrupt from a child task, because the node
    would replay its non-completed siblings on resume. The graph-level per-subtask
    gate asks first; `confirmed=True` says that gate already got the user's yes.
    """
    from ze_core.telemetry.context import set_agent_context

    set_agent_context(agent_name)

    instance = get_agent(agent_name)
    timeout = float(getattr(instance, "timeout", 30))

    if token_queue is not None:

        async def _stream_and_collect() -> AgentResult:
            tokens: list[str] = []
            try:
                async for token in instance.stream(ctx):
                    tokens.append(token)
                    await token_queue.put(token)
            finally:
                await token_queue.put(None)
            return AgentResult(agent=agent_name, response="".join(tokens))

        try:
            return await asyncio.wait_for(_stream_and_collect(), timeout=timeout)
        except asyncio.TimeoutError:
            if has_budget(ctx):
                return _out_of_time(agent_name, ctx)
            raise AgentTimeoutError(f"{agent_name} timed out after {timeout}s")

    try:
        result = await asyncio.wait_for(instance.run(ctx), timeout=timeout)
        if ctx.sources:
            add_sources(result.sources, ctx.sources)
        return result
    except asyncio.TimeoutError:
        if has_budget(ctx):
            return _out_of_time(agent_name, ctx)
        raise AgentTimeoutError(f"{agent_name} timed out after {timeout}s")


def _out_of_time(agent_name: str, ctx: AgentContext) -> AgentResult:
    """A conductor past its hard limit still answers: what was done, what was not."""
    log.warning("conductor_hard_timeout", agent=agent_name)
    return AgentResult(
        agent=agent_name,
        response=partial_answer(ctx.conductor_ledger),
        tool_calls=list(ctx.tool_calls),
    )
