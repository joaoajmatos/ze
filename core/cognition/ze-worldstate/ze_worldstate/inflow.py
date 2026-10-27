from __future__ import annotations

from typing import Any

from ze_worldstate.admission import LoopInflow


def make_loop_inflow_from_parts(
    *,
    lifecycle: Any,
    loop_store: Any,
    loop_graph_store: Any,
    loop_entity_resolver: Any,
    openrouter_client: Any,
    embedder: Any,
    system_one_client: Any = None,
    settings: Any = None,
) -> LoopInflow:
    return LoopInflow(
        lifecycle=lifecycle,
        loop_store=loop_store,
        graph_store=loop_graph_store,
        entity_resolver=loop_entity_resolver,
        llm_client=openrouter_client,
        embedder=embedder,
        system_one_client=system_one_client,
        settings=settings,
    )


def make_loop_extractor_from_parts(
    *,
    lifecycle: Any,
    loop_store: Any,
    loop_graph_store: Any,
    loop_entity_resolver: Any,
    openrouter_client: Any,
    embedder: Any,
    system_one_client: Any = None,
    settings: Any = None,
):
    """Builds an async `(text, provenance, evidence=()) -> None` callable, for wiring into
    inflow modules (ze-messenger, ze-calendar, ze-ingestion) that must not import
    `ze_worldstate` directly (plan.md: ze-api is the only wiring point for FR-017's
    direct-write proto-contribution). Judges with the loop gate, logs, then commits.
    """
    return make_loop_inflow_from_parts(
        lifecycle=lifecycle,
        loop_store=loop_store,
        loop_graph_store=loop_graph_store,
        loop_entity_resolver=loop_entity_resolver,
        openrouter_client=openrouter_client,
        embedder=embedder,
        system_one_client=system_one_client,
        settings=settings,
    ).extract


def make_loop_extractor(container: Any):
    """Same as `make_loop_extractor_from_parts`, sourced from a built `ZeContainer`."""
    return make_loop_extractor_from_parts(
        lifecycle=container.loop_lifecycle,
        loop_store=container.loop_store,
        loop_graph_store=container.loop_graph_store,
        loop_entity_resolver=container.loop_entity_resolver,
        openrouter_client=container.openrouter_client,
        embedder=container.embedder,
        system_one_client=getattr(container, "system_one_client", None),
        settings=getattr(container, "settings", None),
    )
