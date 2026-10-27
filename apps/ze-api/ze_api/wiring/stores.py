from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ze_automation.action_records import (
    configure_action_recorder as configure_automation_action_recorder,
)
from ze_collision.store import PostgresCollisionLogStore
from ze_core.bootstrap import EngineStack
from ze_core.conversation.confirmations import PendingConfirmationStore
from ze_core.conversation.messages import PostgresMessageStore
from ze_core.conversation.sessions import PostgresSessionStore
from ze_memory.action_records.store import PostgresActionRecordStore
from ze_memory.dream.store import PostgresDreamStore
from ze_memory.feedback_records import PostgresFeedbackStore
from ze_personal.channels.thread_channel_map import ThreadChannelMap
from ze_personal.channels.user_channel_store import UserChannelStore
from ze_personal.channels.watermark_store import ChannelWatermarkStore
from ze_personal.contacts.channel_store import ContactChannelStore
from ze_personal.persona.postgres import PostgresPersonaStore
from ze_priority.store import PostgresPriorityOverrideStore
from ze_proactive.job_run_store import JobRunStore
from ze_proactive.notification_store import NotificationStore
from ze_proactive.quiet_hours import InterruptionSettingsStore
from ze_api.settings import Settings


@dataclass(kw_only=True)
class CoreStores:
    """Postgres-backed stores that need only the pool (and, for procedures, the embedder)."""

    priority_override_store: PostgresPriorityOverrideStore
    collision_store: PostgresCollisionLogStore
    action_record_store: PostgresActionRecordStore
    procedure_store: Any
    procedure_admission: Any
    procedure_discovery: Any
    procedure_activator: Any
    message_store: PostgresMessageStore
    session_store: PostgresSessionStore
    confirmation_store: PendingConfirmationStore
    feedback_store: PostgresFeedbackStore
    interruption_settings_store: InterruptionSettingsStore
    notification_store: NotificationStore
    job_run_store: JobRunStore
    persona_store: PostgresPersonaStore
    dream_store: PostgresDreamStore
    user_channel_store: UserChannelStore
    watermark_store: ChannelWatermarkStore
    thread_channel_map: ThreadChannelMap
    contact_channel_store: ContactChannelStore


def build_stores(pool: Any, shared: EngineStack, settings: Settings) -> CoreStores:
    action_record_store = PostgresActionRecordStore(pool=pool)
    configure_automation_action_recorder(action_record_store)

    from ze_memory.procedures.activation import ProcedureActivator
    from ze_memory.procedures.admission import ProcedureAdmissionService
    from ze_memory.procedures.discovery import ProcedureDiscovery
    from ze_memory.procedures.store import PostgresProcedureStore

    procedure_store = PostgresProcedureStore(pool, embedder=shared.embedder)
    procedure_activator = ProcedureActivator(procedure_store)
    import ze_memory.procedures.tools as procedure_tools

    procedure_tools.configure(activator=procedure_activator)

    persona_cfg = settings.persona_config
    return CoreStores(
        priority_override_store=PostgresPriorityOverrideStore(pool=pool),
        collision_store=PostgresCollisionLogStore(pool=pool),
        action_record_store=action_record_store,
        procedure_store=procedure_store,
        procedure_admission=ProcedureAdmissionService(procedure_store),
        procedure_discovery=ProcedureDiscovery(procedure_store),
        procedure_activator=procedure_activator,
        message_store=PostgresMessageStore(pool=pool),
        session_store=PostgresSessionStore(pool=pool),
        confirmation_store=PendingConfirmationStore(pool=pool),
        feedback_store=PostgresFeedbackStore(pool),
        interruption_settings_store=InterruptionSettingsStore(pool),
        notification_store=NotificationStore(pool=pool),
        job_run_store=JobRunStore(pool),
        persona_store=PostgresPersonaStore(
            pool=pool,
            profiles=persona_cfg.get("profiles", {}),
            default_profile=persona_cfg.get("profile", "default"),
        ),
        dream_store=PostgresDreamStore(pool=pool),
        user_channel_store=UserChannelStore(pool=pool),
        watermark_store=ChannelWatermarkStore(pool=pool),
        thread_channel_map=ThreadChannelMap(pool=pool),
        contact_channel_store=ContactChannelStore(pool=pool),
    )
