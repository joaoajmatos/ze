from __future__ import annotations

from dataclasses import replace

from langchain_core.runnables import RunnableConfig
from ze_logging import get_logger
from ze_core.conversation.messages.judgments import judgments_from_result
from ze_core.orchestration.judgment_bars import bar_map
from ze_core.orchestration.state import AgentState
from ze_core.orchestration.judgment_state import build_judgment_state, history_hint
from ze_agents.registry import get_enabled_agents
from ze_core.screen.owners import screen_owner
from ze_core.routing.tier import resolve_agent_model
from ze_core.routing.types import RoutingEnvelope, SubTask
from ze_core.telemetry.context import get_cost_context, set_agent_context

log = get_logger(__name__)


async def embed_route(state: AgentState, config: RunnableConfig) -> dict:
    from ze_core.routing.router import EmbeddingRouter

    router: EmbeddingRouter = config["configurable"]["router"]

    # preprocess has already set image_caption for image turns; use it for routing
    routing_text = state.get("image_caption") or state["prompt"]

    # Append after the message so the actual message content dominates the embedding
    hint = history_hint(state)
    if hint:
        routing_text = f"{routing_text}\n\n{hint}"

    hints = state.get("routing_hints")
    if hints:
        routing_text = f"{routing_text}\n\n{hints}"

    screen_line = (
        state.get("screen_subject_line")
        if getattr(router, "screen_hint", False)
        else None
    )
    judgment_state = build_judgment_state(state, screen_line)
    previous_agent = get_cost_context().agent
    set_agent_context("router")
    forced_agent = config["configurable"].get("forced_agent")
    screen_agent = (
        None
        if forced_agent
        else screen_owner(
            config["configurable"].get("screen_context"), set(get_enabled_agents())
        )
    )
    try:
        if forced_agent:
            envelope = await router.route_forced(
                routing_text, state["session_id"], forced_agent
            )
        elif screen_agent:
            envelope = await router.route_forced(
                routing_text, state["session_id"], screen_agent, method="screen"
            )
        else:
            envelope = await router.route(
                prompt=routing_text,
                session_id=state["session_id"],
                judgment_state=judgment_state,
            )
    finally:
        set_agent_context(previous_agent)
    log.info(
        "orchestration_routed",
        session_id=state["session_id"],
        primary_agent=envelope.primary_agent,
        routing_method=envelope.routing_method,
        is_compound=envelope.is_compound,
    )
    judgment = envelope.judgment
    rows = (
        judgments_from_result(
            judgment.result,
            question_kinds=judgment.question_kinds,
            consumed=judgment.consumed,
            skip_reason=judgment.skip_reason,
            surface="routing",
            bars=bar_map(
                router.surface,
                {"agent": "choice_trust", "multi_specialist": "multi_specialist_hold"},
            ),
        )
        if judgment is not None
        else []
    )
    return {"envelope": envelope, "judgments": rows}


async def decompose(state: AgentState, config: RunnableConfig) -> dict:
    from ze_agents.registry import get_enabled_agents
    from ze_core.routing import fallback
    from ze_core.routing.router import EmbeddingRouter

    set_agent_context("router")
    client = config["configurable"]["openrouter_client"]
    router: EmbeddingRouter | None = config["configurable"].get("router")

    fallback_model = "anthropic/claude-haiku-4-5"
    if router is not None:
        fallback_model = router._config.fallback_model

    envelope = state.get("envelope")
    raw_scores: dict = envelope.raw_scores if envelope else {}

    # Give the LLM fallback the same history-enriched text that the embedding
    # router saw, so anaphoric follow-ups route correctly even at low confidence.
    prompt_for_fallback = state["prompt"]
    hint = history_hint(state)
    if hint:
        prompt_for_fallback = f"{prompt_for_fallback}\n\n{hint}"
    routing_hints = state.get("routing_hints")
    if routing_hints:
        prompt_for_fallback = f"{prompt_for_fallback}\n\n{routing_hints}"

    new_envelope = await fallback.decompose(
        prompt=prompt_for_fallback,
        raw_scores=raw_scores,
        client=client,
        agent_registry=get_enabled_agents(),
        fallback_model=fallback_model,
        logger=log,
    )

    if router is not None:
        new_envelope = replace(
            new_envelope,
            threshold=router.config.threshold,
            gap_threshold=router.config.gap_threshold,
        )

    log.info(
        "orchestration_decomposed",
        session_id=state["session_id"],
        subtask_count=len(new_envelope.subtasks),
        is_sequential=new_envelope.is_sequential,
    )
    rewritten, hint = apply_conductor_rewrite(new_envelope, state["prompt"])
    if router is not None:
        for subtask in rewritten.subtasks:
            subtask.model = resolve_agent_model(
                subtask.agent, "full", router._app_config
            )
    ledger = [{"agent": h["agent"], "status": "planned"} for h in hint] if hint else []
    if hint is not None:
        log.info(
            "conductor_rewrite",
            session_id=state["session_id"],
            specialists=[h["agent"] for h in hint],
        )
    return {
        "envelope": rewritten,
        "conductor_hint": hint,
        "conductor_ledgers": [ledger],
    }


def is_mixed_gather_act(subtasks: list[SubTask]) -> bool:
    """True when more than one specialist and the turn both gathers and changes things."""
    agents = {s.agent for s in subtasks}
    if len(agents) <= 1:
        return False
    return any(s.changes for s in subtasks) and any(not s.changes for s in subtasks)


def apply_conductor_rewrite(
    envelope: RoutingEnvelope, user_prompt: str
) -> tuple[RoutingEnvelope, list[dict[str, str]] | None]:
    """Sequential multi or mixed gather+act turns become companion-primary; hint is not a DAG."""
    sequential_multi = envelope.is_sequential and len(envelope.subtasks) > 1
    mixed = is_mixed_gather_act(envelope.subtasks)
    if not sequential_multi and not mixed:
        return envelope, None
    hint = [
        {"agent": s.agent, "prompt": s.prompt, "changes": s.changes}
        for s in envelope.subtasks
    ]
    rewritten = RoutingEnvelope(
        primary_agent="companion",
        confidence=envelope.confidence,
        score_gap=envelope.score_gap,
        routing_method=envelope.routing_method,
        is_compound=False,
        subtasks=[SubTask(agent="companion", prompt=user_prompt)],
        requires_synthesis=False,
        raw_scores=envelope.raw_scores,
        is_sequential=True,
        threshold=envelope.threshold,
        gap_threshold=envelope.gap_threshold,
    )
    return rewritten, hint
