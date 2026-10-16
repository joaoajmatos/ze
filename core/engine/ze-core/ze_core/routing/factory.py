"""The one place an ``EmbeddingRouter`` is built for production wiring."""

from __future__ import annotations

from typing import Any

from ze_agents.defaults import (
    MODEL_ROUTER_FALLBACK,
    ROUTING_GAP_THRESHOLD,
    ROUTING_THRESHOLD,
)
from ze_agents.model_resolution import resolve_model

from ze_core.routing.judge import routing_surface_config
from ze_core.routing.router import EmbeddingRouter
from ze_core.routing.store import RoutingStore
from ze_core.routing.tier import (
    ComplexitySurfaceConfig,
    TierJudge,
    complexity_surface_config,
)
from ze_core.routing.types import RouterConfig


def router_config_from(config: dict) -> RouterConfig:
    routing = config.get("routing") or {}
    return RouterConfig(
        threshold=routing.get("threshold", ROUTING_THRESHOLD),
        gap_threshold=routing.get("gap_threshold", ROUTING_GAP_THRESHOLD),
        fallback_model=resolve_model("router_fallback", MODEL_ROUTER_FALLBACK, config),
    )


def build_embedding_router(
    *,
    embedder: Any,
    openrouter_client: Any,
    config: dict,
    system_one_client: Any,
    routing_store: RoutingStore | None = None,
) -> EmbeddingRouter:
    return EmbeddingRouter(
        embedder=embedder,
        openrouter_client=openrouter_client,
        routing_store=routing_store,
        config=router_config_from(config),
        app_config=config,
        system_one_client=system_one_client,
        surface=routing_surface_config(config),
    )


def build_tier_judge(*, config: dict, system_one_client: Any) -> TierJudge:
    surface = complexity_surface_config(config)
    system_one = config.get("system_one")
    if not (isinstance(system_one, dict) and system_one.get("enabled") is True):
        surface = ComplexitySurfaceConfig(enabled=False, simple_max=surface.simple_max)
    return TierJudge(system_one_client, surface, config)
