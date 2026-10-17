from __future__ import annotations

from typing import Any

from sentence_transformers import SentenceTransformer

from ze_agents.bootstrap import bootstrap_agents
from ze_agents.nli import NLIClient
from ze_agents.progress.translations import ProgressTranslations
from ze_agents.settings import Settings as CoreSettings
from ze_agents.system_one import SystemOneClient
from ze_automation.bootstrap import (
    AutomationStack,
    import_agent_modules as import_automation_agents,
)
from ze_browser import BrowserClient
from ze_collision.store import CollisionLogStore
from ze_communication.registry import ChannelRegistry
from ze_core.bootstrap import EngineStack
from ze_core.nli import LocalNLIClient
from ze_correlation.bootstrap import CorrelationStack
from ze_correlation.store import PostgresHypothesisStore
from ze_ingestion.bootstrap import import_agent_modules as import_ingestion_agents
from ze_logging import get_logger
from ze_memory.action_records.store import ActionRecordStore, PostgresActionRecordStore
from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_onboarding import (
    CoreOnboardingProvider,
    OnboardingCoordinator,
    PostgresOnboardingPersistence as OnboardingPersistence,
    PostgresOnboardingStore as OnboardingStore,
)
from ze_plugin.ui import collect_ui_contributions, filter_ui_manifest_by_openapi
from ze_priority import WorldComposer, import_agent_modules as import_priority_agents
from ze_priority.store import PriorityOverrideStore
from ze_priority.view import PriorityView
from ze_proactive.notification_store import NotificationStore
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.push_log_store import PushLogStore
from ze_personal.channels.thread_channel_map import ThreadChannelMap
from ze_personal.channels.user_channel_store import UserChannelStore
from ze_personal.channels.watermark_store import ChannelWatermarkStore
from ze_personal.contacts.channel_store import ContactChannelStore
from ze_skills.bootstrap import SkillsStack, register_bundled_skills
from ze_workspace.bootstrap import WorkspaceStack
from ze_workspace.client import WorkspaceClient
from ze_workspace.gate import WorkspaceGate
from ze_workspace.store import WorkspaceStore
from ze_worldstate.bootstrap import import_agent_modules as import_worldstate_agents
from ze_worldstate.tracking import LoopTracker
from ze_api.cli.openapi_export import collect_openapi_operation_ids
from ze_api.settings import Settings
from ze_api.wiring.stores import CoreStores
from ze_api.wiring.webhooks import (
    EventDeduplicator,
    WebhookDispatcher,
    collect_plugin_webhook_handlers,
)

log = get_logger(__name__)


def build_dep_map(
    shared: EngineStack,
    settings: Settings,
    *,
    notifier: ProactiveNotifier,
    stores: CoreStores,
    browser_client: BrowserClient,
    workspace: WorkspaceStack,
    priority_view: PriorityView,
    correlation: CorrelationStack,
    loop_tracker: LoopTracker,
    world_composer: WorldComposer,
) -> dict[type, Any]:
    """Constructor-injection map handed to plugins and agents."""
    dep_map = dict(shared.dep_map)
    dep_map.update(
        {
            Settings: settings,
            CoreSettings: shared.core_settings,
            ProactiveNotifier: notifier,
            PushLogStore: stores.push_log_store,
            NotificationStore: stores.notification_store,
            SentenceTransformer: shared.embedder,
            NLIClient: shared.nli_client,
            LocalNLIClient: shared.nli_client,
            SystemOneClient: shared.system_one_client,
            BrowserClient: browser_client,
            WorkspaceClient: workspace.client,
            WorkspaceGate: workspace.gate,
            WorkspaceStore: workspace.store,
            UserChannelStore: stores.user_channel_store,
            ChannelWatermarkStore: stores.watermark_store,
            ThreadChannelMap: stores.thread_channel_map,
            ContactChannelStore: stores.contact_channel_store,
            PriorityView: priority_view,
            PriorityOverrideStore: stores.priority_override_store,
            CollisionLogStore: stores.collision_store,
            PostgresHypothesisStore: correlation.hypothesis_store,
            ActionRecordStore: stores.action_record_store,
            PostgresActionRecordStore: stores.action_record_store,
            ProcedureAdmissionService: stores.procedure_admission,
            LoopTracker: loop_tracker,
            WorldComposer: world_composer,
        }
    )
    return dep_map


def build_translations(settings: Settings, plugins: list) -> ProgressTranslations:
    locale: str = settings.config.get("locale", "en")
    en_layers = [p.locale_data("en") for p in plugins]
    target_layers = (
        [p.locale_data(locale) for p in plugins] if locale != "en" else en_layers
    )
    app_en = ProgressTranslations._load_file(
        settings.config_dir / "locales" / "en.yaml"
    )
    app_locale = (
        ProgressTranslations._load_file(
            settings.config_dir / "locales" / f"{locale}.yaml"
        )
        if locale != "en"
        else app_en
    )
    translations = ProgressTranslations.build(
        layers=target_layers + [app_locale],
        fallback_layers=en_layers + [app_en],
    )
    log.info("progress_translations_built", locale=locale)
    return translations


def build_onboarding_coordinator(
    pool: Any, shared: EngineStack, plugins: list
) -> OnboardingCoordinator:
    providers = [CoreOnboardingProvider()]
    for plugin in plugins:
        provider = plugin.onboarding()
        if provider is not None:
            providers.append(provider)
            log.info(
                "onboarding_provider_registered",
                plugin=provider.plugin_name,
                priority=provider.priority,
            )
    return OnboardingCoordinator(
        providers=providers,
        store=OnboardingStore(pool=pool),
        persistence=OnboardingPersistence(memory_store=shared.memory_store),
    )


def build_channels_and_webhooks(
    plugins: list,
) -> tuple[ChannelRegistry, WebhookDispatcher, dict]:
    """Channels come from plugins; build the registry before agent bootstrap so
    MessengerAgent can receive it via dep injection."""
    channel_registry = ChannelRegistry(
        channels=[ch for plugin in plugins for ch in plugin.channels()]
    )
    log.info("channel_registry_built", channels=list(channel_registry.available()))

    plugin_webhook_handlers = collect_plugin_webhook_handlers(plugins)
    webhook_dispatcher = WebhookDispatcher(
        channel_registry=channel_registry,
        plugin_handlers=plugin_webhook_handlers,
        container=None,  # back-filled after container construction
        deduplicator=EventDeduplicator(),
    )
    if plugin_webhook_handlers:
        log.info("webhook_handlers_registered", keys=list(plugin_webhook_handlers))
    return channel_registry, webhook_dispatcher, plugin_webhook_handlers


def build_agent_deps(
    dep_map: dict[type, Any], channel_registry: ChannelRegistry, plugins: list
) -> dict[type, Any]:
    agent_deps: dict[type, Any] = dict(dep_map)
    agent_deps[ChannelRegistry] = channel_registry
    for plugin in plugins:
        agent_deps.update(plugin.agent_deps(agent_deps))
    return agent_deps


def collect_plugin_stores(
    plugins: list,
    stores: CoreStores,
    automation: AutomationStack,
    priority_view: PriorityView,
) -> dict:
    plugin_stores: dict = {}
    for plugin in plugins:
        plugin_stores.update(plugin.rest_stores())
    plugin_stores["procedure_admission"] = stores.procedure_admission
    plugin_stores["goal_suggestion_store"] = automation.goal_suggestion_store
    plugin_stores["goal_planner"] = automation.goal_planner

    person_store = plugin_stores.get("person_store")
    if person_store is not None:
        priority_view.set_relationship_source(person_store)
    return plugin_stores


def collect_plugin_signal_sources(plugins: list) -> dict:
    from ze_agents.errors import AgentConfigError

    sources: dict = {}
    for plugin in plugins:
        for source in plugin.signal_sources():
            if source.source_key in sources:
                raise AgentConfigError(
                    f"Duplicate signal source key {source.source_key!r} "
                    f"contributed by {type(plugin).__name__}"
                )
            sources[source.source_key] = source
    if sources:
        log.info("signal_sources_collected", keys=list(sources))
    return sources


def build_ui_manifest(plugins: list) -> Any:
    ui_manifest = collect_ui_contributions(plugins)
    ui_manifest = filter_ui_manifest_by_openapi(
        ui_manifest,
        collect_openapi_operation_ids(),
    )
    log.info(
        "ui_manifest_built",
        nav=[item.id for item in ui_manifest.nav],
        settings=[item.id for item in ui_manifest.settings_sections],
    )
    return ui_manifest


async def bootstrap_agent_layer(
    agent_deps: dict[type, Any], plugins: list, skills_stack: SkillsStack
) -> None:
    import_automation_agents()
    import_ingestion_agents()
    import_priority_agents()
    import_worldstate_agents()
    bootstrap_agents(deps=agent_deps, plugins=plugins)
    await register_bundled_skills(skills_stack.skill_store, plugins)
