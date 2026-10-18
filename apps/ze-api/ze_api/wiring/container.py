from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import aiohttp

from ze_agents.interface.types import RawInput
from ze_agents.interface.validation import validate_interface
from ze_automation.bootstrap import (
    automation_data_domains,
    build_automation_stack,
    configure_workflow_executor,
)
from ze_worldstate.bootstrap import (
    build_worldstate_stack,
    worldstate_data_domains,
)
from ze_worldstate.store import LoopStore
from ze_worldstate.tracking import LoopTracker
from ze_skills.bootstrap import (
    build_skill_matcher,
    build_skills_stack,
)
from ze_skills.store import SkillStore
from ze_memory.action_records.store import PostgresActionRecordStore
from ze_memory.feedback_records import PostgresFeedbackStore
from ze_memory.feedback_records.data_domain import feedback_data_domains
from ze_personal.channels.user_channel_store import UserChannelStore
from ze_personal.channels.watermark_store import ChannelWatermarkStore
from ze_priority import WorldComposer
from ze_priority.store import PriorityOverrideStore
from ze_browser import BrowserClient
from ze_workspace.bootstrap import build_workspace_stack
from ze_workspace.client import WorkspaceClient
from ze_workspace.followthrough import RunWatcher
from ze_workspace.gate import WorkspaceGate
from ze_workspace.push_kinds import WORKSPACE_RUN_COMPLETED
from ze_workspace.store import WorkspaceStore
from ze_workspace.turn_lock import ThreadTurnLock
from ze_components.hook import ComponentCollectionHook
from ze_core.bootstrap import (
    build_checkpointer,
    build_engine_stack,
    build_router,
    engine_data_domains,
    register_harness_hooks,
)
from ze_core.container import Container as CoreContainer
from ze_core.routing.factory import build_tier_judge
from ze_core.telemetry.budget import SpendBudgetChecker
from ze_core.conversation import (
    TurnResult,
    invoke_raw_turn,
    invoke_retry_turn,
    resume_turn,
)
from ze_core.conversation.confirmations import PendingConfirmationStore
from ze_core.conversation.messages import PostgresMessageStore
from ze_core.conversation.rewind import history_rewindable
from ze_core.conversation.turn import turn_has_reply
from ze_core.conversation.sessions import PostgresSessionStore
from ze_core.orchestration.graph import build_graph
from ze_priority.view import PriorityView
from ze_priority.turn import TurnSurfacing
from ze_data.portability.service import DataPortabilityService
from ze_seed.service import DevDataSeeder, collect_seed_domains
from ze_ingestion.bootstrap import (
    build_ingestion_stack,
)
from ze_memory.policies import build_policy_registry
from ze_notifications.ntfy import NtfyConfig, NtfyNotifier
from ze_onboarding import OnboardingCoordinator
from ze_plugin.bootstrap import discover_and_instantiate_plugins
from ze_communication.registry import ChannelRegistry
from ze_proactive.job_run_store import JobRunStore
from ze_proactive.notification_store import NotificationStore
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.push_log_store import PushLogStore
from ze_proactive.bootstrap import shared_push_budget
from ze_proactive.data_domain import interruption_data_domains
from ze_proactive.quiet_hours import InterruptionSettingsStore, is_active
from ze_proactive.scheduler import ProactiveScheduler
from ze_api.api.ws.connection import ConnectionManager
from ze_api.wiring.jobs import (
    build_proactive_scheduler,
    reconcile_workspace_at_startup,
    register_all_proactive_jobs,
)
from ze_api.wiring.db import create_checkpointer_pool, create_pool
from ze_api.interface.native import NativeAppInterface
from ze_logging import get_logger
from ze_api.settings import Settings, get_settings
from ze_api.wiring.agents import (
    bootstrap_agent_layer,
    build_agent_deps,
    build_channels_and_webhooks,
    build_dep_map,
    build_onboarding_coordinator,
    build_translations,
    build_ui_manifest,
    collect_plugin_signal_sources,
    collect_plugin_stores,
)
from ze_api.wiring.hooks import (
    build_budget_checker,
    build_commitment_intake,
    build_dream_job,
    install_contradiction_hook,
    wire_automation,
    wire_collision_detection,
    wire_ingestion_loop_extractor,
    wire_plugin_consolidators,
    wire_plugin_loop_extractors,
)
from ze_api.wiring.stores import build_stores
from ze_api.wiring.screen import build_screen_registry
from ze_api.wiring.workflow_graph import begin_workflow_turn, build_workflow_graph
from ze_agents.registry import get_registered_agents
from ze_correlation.store import PostgresHypothesisStore
from ze_correlation.bootstrap import (
    build_correlation_push_candidate_source,
    build_correlation_stack,
)
from ze_worldstate.bootstrap import build_loop_surfacer
import ze_components.tools  # noqa: F401 — registers all render tools at import time

log = get_logger(__name__)


class _ContainerTurnStarter:
    """Satisfies ze_workspace.followthrough.TurnStarter — a thin wrapper around
    the lock-aware ZeContainer.invoke_raw_turn (T022/T023). Does not acquire
    ThreadTurnLock itself; container.invoke_raw_turn already does, and a second
    acquire on the same non-reentrant lock would deadlock.

    Built before ZeContainer exists (build_workspace_stack runs early in
    build_container), so the container reference is bound in once available.
    """

    def __init__(self) -> None:
        self._container: ZeContainer | None = None

    def bind(self, container: "ZeContainer") -> None:
        self._container = container

    async def invoke_raw_turn(self, thread_id: str, prompt: str) -> None:
        if self._container is None:
            log.warning("workspace_followup_turn_starter_unbound", thread_id=thread_id)
            return
        outcome = await self._container.invoke_raw_turn(
            thread_id, RawInput(text=prompt)
        )
        if outcome.interrupted or not turn_has_reply(outcome):
            return
        await self._container.interface.send_with_thread(
            outcome.response,
            thread_id=thread_id,
            components=(outcome.final_state or {}).get("components") or None,
            trace=(outcome.final_state or {}).get("message_trace"),
        )


class _NotifierPushSender:
    """Satisfies ze_workspace.followthrough.PushSender via the existing
    ProactiveNotifier — same structured-event path stuck goals/accountability/
    reminders already use (D4), `event_type="workspace_run_completed"` reusing
    the Phase 105 notifications table with no new column. Bound in once the
    notifier exists (built after the workspace stack in build_container)."""

    def __init__(self) -> None:
        self._notifier: ProactiveNotifier | None = None

    def bind(self, notifier: ProactiveNotifier) -> None:
        self._notifier = notifier

    async def send_completion(self, run: Any) -> None:
        if self._notifier is None:
            log.warning("workspace_push_sender_unbound", run_id=str(run.id))
            return
        title = "Workspace run finished"
        body = _push_body(run)
        await self._notifier.notify(
            WORKSPACE_RUN_COMPLETED,
            title,
            body,
            target_type="workspace_run",
            target_id=str(run.id) if run.id else None,
        )


def _push_body(run: Any) -> str:
    status = getattr(run.status, "value", run.status)
    command = run.command
    if status == "cancelled":
        return f"Stopped: {command}"
    if status == "succeeded":
        return f"Finished: {command}"
    if status == "timed_out":
        return f"Timed out: {command}"
    return f"Failed: {command}"


async def _locked_invoke_raw_turn(
    container: Any,
    turn_lock: ThreadTurnLock,
    thread_id: str,
    raw: RawInput,
    *,
    config_extra: dict | None = None,
) -> TurnResult:
    async with turn_lock.acquire(thread_id):
        return await invoke_raw_turn(
            container, thread_id, raw, config_extra=config_extra
        )


async def _locked_resume_turn(
    container: Any,
    turn_lock: ThreadTurnLock,
    config: dict,
    resume: object = None,
    request_id: str | None = None,
) -> TurnResult:
    thread_id = (config.get("configurable") or {}).get("thread_id") or ""
    async with turn_lock.acquire(thread_id):
        return await resume_turn(
            container, config, resume=resume, request_id=request_id
        )


@dataclass(kw_only=True)
class ZeContainer(CoreContainer):
    """Ze application container — ze-core graph stack plus WebSocket, proactive, workflow."""

    translations: Any
    signal_sources: dict
    correlation_engine: Any | None
    persona_store: Any
    workflow_store: Any
    held_write_store: Any
    held_write_resumer: Any
    _plugin_stores: dict
    workflow_scheduler: Any
    proactive_scheduler: ProactiveScheduler
    browser_client: BrowserClient
    workspace_client: WorkspaceClient
    workspace_gate: WorkspaceGate
    workspace_store: WorkspaceStore
    workspace_run_watcher: RunWatcher
    turn_lock: ThreadTurnLock
    push_notifier: NtfyNotifier | None
    message_store: PostgresMessageStore
    feedback_store: PostgresFeedbackStore
    session_store: PostgresSessionStore
    connection_manager: ConnectionManager
    component_hook: ComponentCollectionHook
    confirmation_store: PendingConfirmationStore
    onboarding_coordinator: OnboardingCoordinator
    action_record_store: PostgresActionRecordStore
    user_channel_store: UserChannelStore
    watermark_store: ChannelWatermarkStore
    _checkpointer: Any
    _push_log_store: PushLogStore
    interruption_settings_store: InterruptionSettingsStore
    notifier: ProactiveNotifier
    notification_store: NotificationStore
    data_portability_service: DataPortabilityService
    dev_data_seeder: DevDataSeeder
    ingestion_pipeline: Any
    dream_store: Any
    channel_registry: ChannelRegistry | None
    webhook_dispatcher: Any | None
    ui_manifest: Any
    loop_store: LoopStore
    job_run_store: JobRunStore
    hypothesis_store: PostgresHypothesisStore
    loop_graph_store: Any
    loop_entity_resolver: Any
    loop_surfacer: Any
    turn_surfacer: Any
    world_composer: WorldComposer
    priority_view: PriorityView
    skill_store: SkillStore
    skill_matcher: Any
    priority_override_store: PriorityOverrideStore = None
    collision_store: Any = None
    nli_client: Any = None
    system_one_client: Any = None
    commitment_intake: Any = None
    budget_checker: SpendBudgetChecker | None = None
    procedure_admission: Any = None
    procedure_discovery: Any = None
    procedure_activator: Any = None
    tier_judge: Any = None
    screen_resolvers: Any = None

    def _build_config(self, thread_id: str, **configurable_extra: object) -> dict:
        plugin_services: dict = {}
        for plugin in self.plugins:
            plugin_services.update(plugin.configurable_services())

        from ze_memory.extractor import gather_fact_proposals

        configurable: dict = {
            "thread_id": str(thread_id),
            "router": self.router,
            "tier_judge": self.tier_judge,
            "memory_store": self.memory_store,
            "fact_extractor": gather_fact_proposals,
            "persona_store": self.persona_store,
            "openrouter_client": self.openrouter_client,
            "embedder": self.embedder,
            "settings": self.settings,
            "interface": self.interface,
            "component_hook": self.component_hook,
            "correlation_engine": self.correlation_engine,
            "workflow_store": self.workflow_store,
            "loop_store": self.loop_store,
            "loop_graph_store": self.loop_graph_store,
            "loop_entity_resolver": self.loop_entity_resolver,
            "loop_surfacer": self.loop_surfacer,
            "turn_surfacer": self.turn_surfacer,
            "world_composer": self.world_composer,
            "collision_store": self.collision_store,
            "nli_client": self.nli_client,
            "system_one_client": self.system_one_client,
            "skill_matcher": self.skill_matcher,
            "budget_checker": self.budget_checker,
            "workspace_client": self.workspace_client,
            "workspace_gate": self.workspace_gate,
            "workspace_store": self.workspace_store,
            "procedure_admission": self.procedure_admission,
            "procedure_discovery": self.procedure_discovery,
            "procedure_activator": self.procedure_activator,
            "screen_resolvers": self.screen_resolvers,
            **plugin_services,
        }
        configurable["memory_hooks"] = [*plugin_services.get("memory_hooks", [])]
        if self.commitment_intake is not None:
            configurable["commitment_intake"] = self.commitment_intake.admit
        configurable.update(configurable_extra)
        return {"configurable": configurable}

    async def invoke_raw_turn(
        self,
        thread_id: str,
        raw: RawInput,
        *,
        config_extra: dict | None = None,
    ) -> TurnResult:
        return await _locked_invoke_raw_turn(
            self, self.turn_lock, thread_id, raw, config_extra=config_extra
        )

    def is_thread_locked(self, thread_id: str) -> bool:
        return self.turn_lock.is_locked(thread_id)

    async def invoke_retry_turn(
        self,
        thread_id: str,
        user_text: str,
        *,
        replaces: UUID,
        config_extra: dict | None = None,
    ) -> TurnResult:
        """Run the retry turn. The caller holds `hold_thread` for the whole retry."""
        return await invoke_retry_turn(
            self, thread_id, user_text, replaces=replaces, config_extra=config_extra
        )

    @asynccontextmanager
    async def hold_thread(self, thread_id: str) -> AsyncIterator[None]:
        """Hold the thread's turn lock across a retry: eligibility, undos, regeneration."""
        async with self.turn_lock.acquire(thread_id):
            yield

    async def retry_rewindable(self, thread_id: str) -> bool:
        return await history_rewindable(self.graph, self._build_config(thread_id))

    async def resume_turn(
        self, config: dict, resume: object = None, *, request_id: str | None = None
    ) -> TurnResult:
        return await _locked_resume_turn(
            self, self.turn_lock, config, resume=resume, request_id=request_id
        )

    async def close(self) -> None:
        for plugin in reversed(self.plugins):
            try:
                await plugin.shutdown()
            except Exception as exc:
                log.warning(
                    "plugin_shutdown_failed",
                    plugin=type(plugin).__name__,
                    error=str(exc),
                )
        await self.proactive_scheduler.stop()
        await self.workflow_scheduler.stop()
        await self.browser_client.close()
        await self.workspace_client.close()
        if self.push_notifier is not None:
            await self.push_notifier.close()
        await super().close()

    @classmethod
    async def from_config(
        cls,
        config_dir: Path | None = None,
        *,
        interface: Any | None = None,
    ) -> ZeContainer:
        get_settings.cache_clear()
        settings = Settings(config_dir=config_dir) if config_dir else Settings()
        container = await build_container(settings)
        if interface is not None:
            container.interface = interface
            validate_interface(interface)
        return container


Container = ZeContainer


def _build_push_notifier(settings: Settings) -> NtfyNotifier | None:
    if not settings.ntfy_topic:
        return None
    ntfy_config = NtfyConfig(
        base_url=settings.ntfy_base_url,
        topic=settings.ntfy_topic,
        token=settings.ntfy_token or None,
    )
    notifier = NtfyNotifier(config=ntfy_config, session=aiohttp.ClientSession())
    log.info("ntfy_notifier_registered", topic=settings.ntfy_topic)
    return notifier


async def build_container(settings: Settings) -> ZeContainer:
    pool = await create_pool(settings)
    checkpointer_pool = await create_checkpointer_pool(settings)

    shared = await build_engine_stack(pool, checkpointer_pool, settings)
    automation = build_automation_stack(shared, settings)
    correlation = build_correlation_stack(shared, settings)
    worldstate = build_worldstate_stack(shared, settings)

    stores = build_stores(pool, shared, settings)
    priority_view = PriorityView(
        loop_store=worldstate.loop_store,
        goal_store=automation.goal_store,
        hypothesis_store=correlation.hypothesis_store,
    )

    skills_stack = build_skills_stack(shared, settings)
    skill_matcher = build_skill_matcher(
        skills_stack.skill_store,
        shared.embedder,
        settings,
        system_one_client=shared.system_one_client,
    )
    turn_lock = ThreadTurnLock()
    turn_starter = _ContainerTurnStarter()
    push_sender = _NotifierPushSender()
    loop_tracker = LoopTracker(
        loop_store=worldstate.loop_store,
        graph_store=worldstate.graph_store,
        entity_resolver=worldstate.entity_resolver,
        embedder=shared.embedder,
        collision_store=stores.collision_store,
        nli_client=shared.nli_client,
    )
    workspace = build_workspace_stack(
        shared,
        settings,
        turn_starter=turn_starter,
        push_sender=push_sender,
        action_record_store=stores.action_record_store,
    )
    wire_automation(automation, workspace, stores, shared, worldstate, skills_stack)
    install_contradiction_hook(shared, worldstate)

    browser_client = BrowserClient(
        base_url=settings.browser_service_url,
        timeout=settings.browser_timeout_seconds,
    )
    push_notifier = _build_push_notifier(settings)
    connection_manager = ConnectionManager()

    async def quiet_now() -> bool:
        return is_active(
            await stores.interruption_settings_store.get(), datetime.now(timezone.utc)
        )

    from ze_api.api.ws.held import held_push_frame

    interface = NativeAppInterface(
        message_store=stores.message_store,
        connection_manager=connection_manager,
        notifier=push_notifier,
        quiet_now=quiet_now,
        confirm_frame_for=held_push_frame(automation.held_write_store),
    )
    validate_interface(interface)

    notifier = ProactiveNotifier(
        interface=interface,
        notification_store=stores.notification_store,
        push_log=stores.push_log_store,
        settings_store=stores.interruption_settings_store,
        max_discretionary_per_day=shared_push_budget(settings),
    )
    push_sender.bind(notifier)

    loop_surfacer = build_loop_surfacer(
        worldstate,
        stores.push_log_store,
        getattr(correlation, "relevance_model", None),
        shared.embedder,
        notifier,
    )
    turn_surfacer = TurnSurfacing(
        priority_view=priority_view,
        override_store=stores.priority_override_store,
        graph_store=worldstate.graph_store,
        loop_store=worldstate.loop_store,
        embedder=shared.embedder,
        push_log=stores.push_log_store,
    )
    world_composer = WorldComposer(
        priority_view=priority_view,
        loop_store=worldstate.loop_store,
        goal_store=automation.goal_store,
        workflow_store=automation.workflow_store,
        held_write_store=automation.held_write_store,
        embedder=shared.embedder,
    )
    correlation_push_source = build_correlation_push_candidate_source(
        correlation, notifier, settings, shared.embedder, shared.nli_client
    )

    dep_map = build_dep_map(
        shared,
        settings,
        notifier=notifier,
        stores=stores,
        browser_client=browser_client,
        workspace=workspace,
        priority_view=priority_view,
        correlation=correlation,
        loop_tracker=loop_tracker,
        world_composer=world_composer,
    )

    plugins = discover_and_instantiate_plugins(dep_map, settings)
    ingestion = build_ingestion_stack(
        shared,
        settings,
        plugins,
        browser_client=browser_client,
    )
    import ze_workspace.tools as workspace_tools

    workspace_tools.configure(
        client=workspace.client,
        gate=workspace.gate,
        store=workspace.store,
        settings=settings,
        skill_store=skills_stack.skill_store,
        ingestion_pipeline=ingestion.pipeline,
    )
    import ze_skills.tools as skills_tools

    skills_tools.configure(skill_store=skills_stack.skill_store)
    wire_ingestion_loop_extractor(ingestion, shared, worldstate, settings)

    translations = build_translations(settings, plugins)
    shared.memory_store.apply_policy_registry(build_policy_registry(plugins))
    checkpointer = await build_checkpointer(checkpointer_pool, plugins)
    onboarding_coordinator = build_onboarding_coordinator(pool, shared, plugins)
    channel_registry, webhook_dispatcher, plugin_webhook_handlers = (
        build_channels_and_webhooks(plugins)
    )
    agent_deps = build_agent_deps(dep_map, channel_registry, plugins)
    plugin_stores = collect_plugin_stores(plugins, stores, automation, priority_view)
    signal_sources = collect_plugin_signal_sources(plugins)
    ui_manifest = build_ui_manifest(plugins)

    await bootstrap_agent_layer(agent_deps, plugins, skills_stack)

    router = build_router(shared, settings)
    tier_judge = build_tier_judge(
        config=settings.config, system_one_client=shared.system_one_client
    )
    component_hook = register_harness_hooks(settings, memory_store=shared.memory_store)
    graph = build_graph(checkpointer=checkpointer, plugins=plugins)

    all_domains = (
        engine_data_domains(pool)
        + automation_data_domains(pool)
        + worldstate_data_domains(pool)
        + feedback_data_domains(pool)
        + interruption_data_domains(pool)
        + [d for plugin in plugins for d in plugin.data_domains()]
    )
    data_portability_service = DataPortabilityService(pool=pool, domains=all_domains)
    log.info("data_portability_service_ready", domains=len(all_domains))

    dev_data_seeder = DevDataSeeder(collect_seed_domains(plugins))
    log.info("dev_data_seeder_ready", domains=len(dev_data_seeder._domains))

    wire_collision_detection(shared, correlation, stores)

    screen_resolvers = build_screen_registry(
        goal_store=automation.goal_store,
        workflow_store=automation.workflow_store,
        held_write_store=automation.held_write_store,
        loop_store=worldstate.loop_store,
        memory_store=shared.memory_store,
        graph_store=worldstate.graph_store,
        procedure_store=stores.procedure_store,
        skill_store=skills_stack.skill_store,
        workspace_store=workspace.store,
        hypothesis_store=correlation.hypothesis_store,
        notification_store=stores.notification_store,
        plugins=plugins,
    )

    container = ZeContainer(
        settings=settings,
        pool=pool,
        checkpointer_pool=checkpointer_pool,
        embedder=shared.embedder,
        openrouter_client=shared.openrouter_client,
        router=router,
        tier_judge=tier_judge,
        budget_checker=build_budget_checker(settings, shared),
        memory_store=shared.memory_store,
        memory_consolidator=shared.memory_consolidator,
        graph=graph,
        interface=interface,
        translations=translations,
        signal_sources=signal_sources,
        correlation_engine=correlation.correlation_engine,
        persona_store=stores.persona_store,
        workflow_store=automation.workflow_store,
        held_write_store=automation.held_write_store,
        held_write_resumer=automation.held_write_resumer,
        _plugin_stores=plugin_stores,
        workflow_scheduler=automation.workflow_scheduler,
        proactive_scheduler=build_proactive_scheduler(
            settings, run_store=stores.job_run_store
        ),
        browser_client=browser_client,
        workspace_client=workspace.client,
        workspace_gate=workspace.gate,
        workspace_store=workspace.store,
        workspace_run_watcher=workspace.run_watcher,
        turn_lock=turn_lock,
        push_notifier=push_notifier,
        message_store=stores.message_store,
        feedback_store=stores.feedback_store,
        session_store=stores.session_store,
        connection_manager=connection_manager,
        component_hook=component_hook,
        confirmation_store=stores.confirmation_store,
        onboarding_coordinator=onboarding_coordinator,
        action_record_store=stores.action_record_store,
        user_channel_store=stores.user_channel_store,
        watermark_store=stores.watermark_store,
        plugins=plugins,
        _checkpointer=checkpointer,
        _push_log_store=stores.push_log_store,
        interruption_settings_store=stores.interruption_settings_store,
        notifier=notifier,
        notification_store=stores.notification_store,
        data_portability_service=data_portability_service,
        dev_data_seeder=dev_data_seeder,
        ingestion_pipeline=ingestion.pipeline,
        dream_store=stores.dream_store,
        channel_registry=channel_registry,
        webhook_dispatcher=webhook_dispatcher,
        ui_manifest=ui_manifest,
        loop_store=worldstate.loop_store,
        loop_graph_store=worldstate.graph_store,
        loop_entity_resolver=worldstate.entity_resolver,
        loop_surfacer=loop_surfacer,
        turn_surfacer=turn_surfacer,
        world_composer=world_composer,
        priority_view=priority_view,
        skill_store=skills_stack.skill_store,
        skill_matcher=skill_matcher,
        priority_override_store=stores.priority_override_store,
        collision_store=stores.collision_store,
        nli_client=shared.nli_client,
        system_one_client=shared.system_one_client,
        commitment_intake=build_commitment_intake(
            shared, worldstate, stores, settings
        ),
        procedure_admission=stores.procedure_admission,
        procedure_discovery=stores.procedure_discovery,
        procedure_activator=stores.procedure_activator,
        screen_resolvers=screen_resolvers,
        job_run_store=stores.job_run_store,
        hypothesis_store=correlation.hypothesis_store,
    )

    webhook_dispatcher._container = container
    turn_starter.bind(container)

    for plugin in plugins:
        try:
            await plugin.startup(container)
            log.info("plugin_started", plugin=type(plugin).__name__)
        except Exception as exc:
            log.error(
                "plugin_startup_failed", plugin=type(plugin).__name__, error=str(exc)
            )
            raise

    wire_plugin_consolidators(plugins, shared, stores)
    wire_plugin_loop_extractors(container)

    await configure_workflow_executor(
        automation,
        shared,
        plugins,
        settings=settings,
        notifier=notifier,
        push_log_store=stores.push_log_store,
        checkpointer=checkpointer,
        router=router,
        persona_store=stores.persona_store,
        workflow_graph_builder=build_workflow_graph,
        begin_workflow_turn=begin_workflow_turn,
        workspace_gate=workspace.gate,
    )

    register_all_proactive_jobs(
        container.proactive_scheduler,
        settings=settings,
        core_settings=shared.core_settings,
        automation=automation,
        correlation=correlation,
        worldstate=worldstate,
        loop_surfacer=loop_surfacer,
        priority_view=priority_view,
        correlation_push_source=correlation_push_source,
        skills_stack=skills_stack,
        shared=shared,
        plugins=plugins,
        notifier=notifier,
        push_log_store=stores.push_log_store,
        notification_store=stores.notification_store,
        dream_job=build_dream_job(pool, shared, stores, settings),
        pool=pool,
    )
    await reconcile_workspace_at_startup(workspace.store, workspace.run_watcher)

    await automation.workflow_scheduler.start()
    await container.proactive_scheduler.start()

    log.info(
        "ze_container_ready",
        plugins=[type(plugin).__name__ for plugin in plugins],
        agents=sorted(get_registered_agents()),
        channels=list(channel_registry.available()),
        ui_nav=len(ui_manifest.nav),
        ui_settings=len(ui_manifest.settings_sections),
        signal_sources=sorted(signal_sources),
        webhook_handlers=sorted(plugin_webhook_handlers),
    )

    return container
