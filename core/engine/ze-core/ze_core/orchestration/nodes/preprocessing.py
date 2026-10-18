from __future__ import annotations

import base64
from typing import Any

from langchain_core.runnables import RunnableConfig

from ze_agents.defaults import MODEL_VISION_CAPTION
from ze_logging import get_logger
from ze_core.orchestration.state import AgentState

log = get_logger(__name__)


async def preprocess(state: AgentState, config: RunnableConfig) -> dict:
    """Normalise multimodal input before routing.

    - Image without prompt → vision caption generated for routing; stored as
      image_caption. image_data is preserved for the execution node.
    - Image with prompt → image_caption is set to the user's prompt text.
    - Text-only → no-op pass-through.
    """
    client = config["configurable"]["openrouter_client"]
    cfg = config["configurable"].get("settings") or {}
    models = (
        cfg.get("models", {})
        if isinstance(cfg, dict)
        else getattr(cfg, "config", {}).get("models", {})
    )
    updates: dict = {}

    if state.get("image_data"):
        if not state.get("prompt"):
            model = models.get("vision_caption", MODEL_VISION_CAPTION)
            caption = await _vision_caption(
                state["image_data"], state["image_mime"], client, model
            )
            updates["image_caption"] = caption
            log.info("preprocess_captioned", chars=len(caption))
        else:
            updates["image_caption"] = state["prompt"]

    return updates


async def _vision_caption(
    image_data: bytes,
    image_mime: str | None,
    client: Any,
    model: str,
) -> str:
    mime = image_mime or "image/jpeg"
    message = {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{base64.b64encode(image_data).decode()}",
                    "detail": "low",
                },
            },
            {
                "type": "text",
                "text": "Describe this image in one sentence for intent classification.",
            },
        ],
    }
    return await client.complete(messages=[message], model=model, max_tokens=80)
