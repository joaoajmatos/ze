from __future__ import annotations

from ze_core.logging import get_logger
from ze_core.orchestration.state import AgentState

log = get_logger(__name__)


async def embed_route(state: AgentState, config: dict) -> dict:
    from ze_core.routing.router import EmbeddingRouter

    router: EmbeddingRouter = config["configurable"]["router"]

    # preprocess has already set image_caption for image turns; use it for routing
    routing_text = state.get("image_caption") or state["prompt"]

    envelope = await router.route(prompt=routing_text, session_id=state["session_id"])
    log.info(
        "orchestration_routed",
        session_id=state["session_id"],
        primary_agent=envelope.primary_agent,
        routing_method=envelope.routing_method,
        is_compound=envelope.is_compound,
    )
    return {"envelope": envelope}


async def decompose(state: AgentState, config: dict) -> dict:
    from ze_core.orchestration.registry import get_enabled_agents
    from ze_core.routing import fallback

    client = config["configurable"]["openrouter_client"]
    router = config["configurable"].get("router")

    fallback_model = "anthropic/claude-haiku-4-5"
    if router is not None:
        fallback_model = router._config.fallback_model

    envelope = state.get("envelope")
    raw_scores: dict = envelope.raw_scores if envelope else {}

    new_envelope = await fallback.decompose(
        prompt=state["prompt"],
        raw_scores=raw_scores,
        client=client,
        agent_registry=get_enabled_agents(),
        fallback_model=fallback_model,
        logger=log,
    )

    log.info(
        "orchestration_decomposed",
        session_id=state["session_id"],
        subtask_count=len(new_envelope.subtasks),
        is_sequential=new_envelope.is_sequential,
    )
    return {"envelope": new_envelope}
