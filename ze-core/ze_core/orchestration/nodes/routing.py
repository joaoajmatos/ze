from __future__ import annotations

import base64
from typing import Any

from ze_core.logging import get_logger
from ze_core.orchestration.state import AgentState

log = get_logger(__name__)

_DEFAULT_CAPTION_MODEL = "google/gemini-flash-1.5"


async def _vision_caption(
    image_data: bytes,
    image_mime: str,
    client: Any,
    model: str,
) -> str:
    message = {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_mime};base64,{base64.b64encode(image_data).decode()}",
                    "detail": "low",
                },
            },
            {"type": "text", "text": "Describe this image in one sentence for intent classification."},
        ],
    }
    return await client.complete(messages=[message], model=model, max_tokens=80)


async def embed_route(state: AgentState, config: dict) -> dict:
    from ze_core.routing.router import EmbeddingRouter

    router: EmbeddingRouter = config["configurable"]["router"]
    updates: dict = {}
    routing_text = state["prompt"]

    if state.get("input_modality") == "image" and not state.get("prompt"):
        client = config["configurable"]["openrouter_client"]
        cfg = config["configurable"].get("settings") or {}
        models = cfg.get("models", {}) if isinstance(cfg, dict) else getattr(cfg, "config", {}).get("models", {})
        caption_model = models.get("vision_caption", _DEFAULT_CAPTION_MODEL)
        caption = await _vision_caption(state["image_data"], state["image_mime"], client, caption_model)
        routing_text = caption
        updates["image_caption"] = caption
    elif state.get("input_modality") == "image":
        updates["image_caption"] = state["prompt"]

    envelope = await router.route(prompt=routing_text, session_id=state["session_id"])
    log.info(
        "orchestration_routed",
        session_id=state["session_id"],
        primary_agent=envelope.primary_agent,
        routing_method=envelope.routing_method,
        is_compound=envelope.is_compound,
    )
    updates["envelope"] = envelope
    return updates


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
