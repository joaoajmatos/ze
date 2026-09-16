from __future__ import annotations

from datetime import datetime

from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_logging import get_logger
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace

from ze_memory.action_records.contribution import submit_action_record
from ze_memory.action_records.store import ActionRecordStore
from ze_memory.action_records.types import (
    ActionContext,
    ActionLifecycle,
    ActionOutcome,
    ActionRecord,
    ActionRecordDraft,
    AuthoritativeRef,
    CausalRef,
    NON_TERMINAL_LIFECYCLES,
)

log = get_logger(__name__)


def idempotency_key(
    *,
    producer_kind: str,
    source_record_type: str,
    source_record_id: str,
    action_kind: str,
    lifecycle: ActionLifecycle,
) -> str:
    return (
        f"{producer_kind}:{source_record_type}:{source_record_id}:"
        f"{action_kind}:{lifecycle.value}"
    )


class ActionRecorder:
    """Injected Phase 135 producer boundary. No SQL from callers."""

    def __init__(self, store: ActionRecordStore) -> None:
        self._store = store

    async def record_action(
        self,
        *,
        producer_kind: str,
        source_record_type: str,
        source_record_id: str,
        action_kind: str,
        lifecycle: ActionLifecycle,
        outcome: ActionOutcome | None,
        actor: str,
        producer_plugin: str,
        occurred_at: datetime,
        summary: str,
        context: ActionContext | None = None,
        failure_code: str | None = None,
        provenance: Provenance = Provenance.PROMPT_SUPPLIED,
        confidence_value: float = 1.0,
    ) -> ActionRecord:
        ref = AuthoritativeRef(domain=f"{producer_kind}.{source_record_type}", record_id=str(source_record_id))
        causal: list[CausalRef] = []
        if lifecycle.value not in NON_TERMINAL_LIFECYCLES:
            try:
                listed = await self._store.list(authoritative_ref=ref, limit=20)
            except Exception:
                listed = []
            if isinstance(listed, list):
                for rec in listed:
                    lifecycle_value = getattr(getattr(rec, "lifecycle", None), "value", None)
                    if lifecycle_value in NON_TERMINAL_LIFECYCLES:
                        causal.append(CausalRef(kind="action_record", id=rec.id))
                        break
        draft = ActionRecordDraft(
            idempotency_key=idempotency_key(
                producer_kind=producer_kind,
                source_record_type=source_record_type,
                source_record_id=str(source_record_id),
                action_kind=action_kind,
                lifecycle=lifecycle,
            ),
            action_type=f"{producer_kind}.{action_kind}",
            actor=actor,
            producer_plugin=producer_plugin,
            lifecycle=lifecycle,
            outcome=outcome,
            occurred_at=occurred_at,
            summary=summary,
            authoritative_ref=ref,
            context=context or ActionContext(),
            causal_refs=causal,
            failure_code=failure_code,
        )
        contribution = Contribution(
            claim_kind=ClaimKind.ACTION_RECORD,
            provenance=provenance,
            confidence=Confidence(
                value=confidence_value, decay_profile=DecayProfile.TIME_LINEAR
            ),
            target_face=TargetFace.WORLD,
            source_function=SourceFunction.ACTION,
            action_record=draft,
        )
        return await submit_action_record(self._store, contribution)


async def safe_record_action(
    recorder: ActionRecorder | None,
    **kwargs,
) -> ActionRecord | None:
    if recorder is None:
        return None
    try:
        return await recorder.record_action(**kwargs)
    except Exception as exc:
        log.warning(
            "action_record_delivery_failed",
            producer_plugin=kwargs.get("producer_plugin"),
            action_kind=kwargs.get("action_kind"),
            source_record_id=str(kwargs.get("source_record_id")),
            error=type(exc).__name__,
        )
        return None
