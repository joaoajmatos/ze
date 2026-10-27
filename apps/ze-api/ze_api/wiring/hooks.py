from __future__ import annotations

from typing import Any

from ze_automation.bootstrap import AutomationStack
from ze_core.bootstrap import EngineStack
from ze_core.telemetry.budget import SpendBudgetChecker, SpendBudgetConfig
from ze_correlation.bootstrap import CorrelationStack
from ze_ingestion.bootstrap import IngestionStack
from ze_logging import get_logger
from ze_skills.bootstrap import SkillsStack
from ze_workspace.bootstrap import WorkspaceStack
from ze_worldstate.bootstrap import WorldstateStack
from ze_api.settings import Settings
from ze_api.wiring.stores import CoreStores

log = get_logger(__name__)


def wire_automation(
    automation: AutomationStack,
    workspace: WorkspaceStack,
    stores: CoreStores,
    shared: EngineStack,
    worldstate: WorldstateStack,
    skills_stack: SkillsStack,
) -> None:
    """Hand the goal/workflow engines their cross-package collaborators and merge deps."""
    automation.goal_executor._workspace_gate = workspace.gate
    automation.goal_executor._action_records = stores.action_record_store
    automation.goal_executor._nli = shared.nli_client
    automation.goal_executor._procedures = stores.procedure_admission
    automation.goal_planner._discovery = stores.procedure_discovery
    automation.workflow_planner._discovery = stores.procedure_discovery
    automation.goal_store._action_records = stores.action_record_store
    automation.goal_store._memory_store = shared.memory_store
    shared.dep_map.update(automation.deps)
    shared.dep_map.update(worldstate.deps)
    shared.dep_map.update(skills_stack.deps)
    shared.dep_map.update(workspace.deps)


def install_contradiction_hook(shared: EngineStack, worldstate: WorldstateStack) -> None:
    async def _worldstate_contradiction_hook(fact_id) -> None:
        await worldstate.lifecycle.decay_from_evidence("fact", fact_id)

    shared.memory_consolidator.contradiction_hook = _worldstate_contradiction_hook


def wire_ingestion_loop_extractor(
    ingestion: IngestionStack,
    shared: EngineStack,
    worldstate: WorldstateStack,
    settings: Settings,
) -> None:
    from ze_worldstate.inflow import make_loop_extractor_from_parts

    ingestion.memory_sink.loop_extractor = make_loop_extractor_from_parts(
        loop_store=worldstate.loop_store,
        loop_graph_store=worldstate.graph_store,
        loop_entity_resolver=worldstate.entity_resolver,
        openrouter_client=shared.openrouter_client,
        embedder=shared.embedder,
        loop_memory_store=shared.memory_store,
        system_one_client=shared.system_one_client,
        settings=settings,
    )


def build_budget_checker(
    settings: Settings, shared: EngineStack
) -> SpendBudgetChecker | None:
    budget_cfg = settings.config.get("budget", {}) or {}
    session_limit_usd = budget_cfg.get("session_limit_usd")
    daily_limit_usd = budget_cfg.get("daily_limit_usd")
    if session_limit_usd is None and daily_limit_usd is None:
        return None
    return SpendBudgetChecker(
        cost_store=shared.cost_store,
        config=SpendBudgetConfig(
            session_limit_usd=session_limit_usd,
            daily_limit_usd=daily_limit_usd,
        ),
    )


def build_commitment_intake(
    shared: EngineStack,
    worldstate: WorldstateStack,
    stores: CoreStores,
    settings: Settings,
) -> Any:
    from ze_worldstate.inflow import make_loop_inflow_from_parts
    from ze_worldstate.intake import CommitmentIntake

    return CommitmentIntake(
        loop_inflow=make_loop_inflow_from_parts(
            loop_store=worldstate.loop_store,
            loop_graph_store=worldstate.graph_store,
            loop_entity_resolver=worldstate.entity_resolver,
            openrouter_client=shared.openrouter_client,
            embedder=shared.embedder,
            loop_memory_store=shared.memory_store,
            collision_store=stores.collision_store,
            nli_client=shared.nli_client,
            system_one_client=shared.system_one_client,
            settings=settings,
        ),
        loop_store=worldstate.loop_store,
        graph_store=worldstate.graph_store,
        entity_resolver=worldstate.entity_resolver,
        embedder=shared.embedder,
        system_one_client=shared.system_one_client,
        settings=settings,
    )


def wire_collision_detection(
    shared: EngineStack,
    correlation: CorrelationStack,
    stores: CoreStores,
    worldstate: WorldstateStack,
) -> None:
    shared.memory_store._collision_store = stores.collision_store
    worldstate.lifecycle.collision_store = stores.collision_store
    correlation.correlation_engine._collision_store = stores.collision_store
    correlation.correlation_engine._nli_client = shared.nli_client


def wire_plugin_consolidators(
    plugins: list, shared: EngineStack, stores: CoreStores
) -> None:
    for plugin in plugins:
        consolidator = getattr(plugin, "contacts_consolidator", None)
        if consolidator is not None:
            consolidator._collision_store = stores.collision_store
            consolidator._nli_client = shared.nli_client


def wire_plugin_loop_extractors(container: Any) -> None:
    """Give the messenger webhook processor and calendar reminder job a loop extractor."""
    webhook_processor = getattr(container, "_webhook_processor", None)
    calendar_reminder_job = getattr(container, "_calendar_reminder_job", None)
    if (
        webhook_processor is not None and hasattr(webhook_processor, "loop_extractor")
    ) or (
        calendar_reminder_job is not None
        and hasattr(calendar_reminder_job, "loop_extractor")
    ):
        from ze_worldstate.inflow import make_loop_extractor

        loop_extractor = make_loop_extractor(container)
        if webhook_processor is not None:
            webhook_processor.loop_extractor = loop_extractor
            log.info("messenger_loop_extractor_wired")
        if calendar_reminder_job is not None:
            calendar_reminder_job.loop_extractor = loop_extractor
            log.info("calendar_loop_extractor_wired")


def build_dream_job(
    pool: Any,
    shared: EngineStack,
    stores: CoreStores,
    settings: Settings,
) -> Any:
    from ze_memory.dream.job import DreamJob

    dream_job = DreamJob(
        pool=pool,
        embedder=shared.embedder,
        consolidator=shared.memory_consolidator,
        dream_store=stores.dream_store,
        client=shared.openrouter_client,
        nli_client=shared.nli_client,
        settings=settings,
        procedure_admission=stores.procedure_admission,
    )
    if dream_job._dream_pass is not None:
        dream_job._dream_pass._collision_store = stores.collision_store
    return dream_job
