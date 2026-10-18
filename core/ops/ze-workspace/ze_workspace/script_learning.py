from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from ze_agents.claims import Provenance
from ze_agents.scripts import ScriptOutcome
from ze_logging import get_logger
from ze_memory.action_records.recorder import ActionRecorder
from ze_memory.action_records.store import ActionRecordStore
from ze_memory.action_records.types import (
    ActionContext,
    ActionLifecycle,
    ActionOutcome,
)
from ze_memory.procedures.types import ProcedureCandidate, ProcedureSourceKind
from ze_plugin.contribution import EvidenceRef

log = get_logger(__name__)

_STREAK = 3
_NAME_MAX = 120
_TRIGGER_MAX = 120
_NOT_RUN = {"busy", "unavailable"}


def tool_signature(agent: str, tools: list[str]) -> str:
    """Stable key for one agent's script shape: its distinct tools in first-call order."""
    distinct = list(dict.fromkeys(tools))
    return hashlib.sha256("\n".join([agent, *distinct]).encode()).hexdigest()


def _lifecycle(status: str) -> tuple[ActionLifecycle, ActionOutcome, str | None]:
    if status == "ok":
        return ActionLifecycle.SUCCEEDED, ActionOutcome.SUCCESS, None
    if status == "timeout":
        return ActionLifecycle.TIMED_OUT, ActionOutcome.TIMEOUT, status
    return ActionLifecycle.FAILED, ActionOutcome.FAILURE, status


def _uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except ValueError:
        return None


class ScriptLearning:
    """Records each finished script on the action ledger; a script that succeeds
    three times in a row becomes a procedure candidate."""

    def __init__(self, *, action_record_store: ActionRecordStore, admission) -> None:
        self._store = action_record_store
        self._recorder = ActionRecorder(action_record_store)
        self._admission = admission

    async def record(
        self,
        *,
        script_id: str,
        agent: str,
        source: str,
        outcome: ScriptOutcome,
        tools: list[str],
        procedure_id: str | None = None,
        message_id: str | UUID | None = None,
        thread_id: str | UUID | None = None,
        user_turn: str | None = None,
    ) -> None:
        if outcome.status in _NOT_RUN:
            return
        distinct = list(dict.fromkeys(tools))
        key = tool_signature(agent, tools)
        lifecycle, result, failure_code = _lifecycle(outcome.status)
        try:
            await self._recorder.record_action(
                producer_kind="workspace",
                source_record_type="tool_script",
                source_record_id=script_id,
                action_kind="run",
                lifecycle=lifecycle,
                outcome=result,
                actor=agent,
                producer_plugin="ze-workspace",
                occurred_at=datetime.now(timezone.utc),
                summary=f"Script by {agent}: {len(tools)} tool calls",
                context=ActionContext(
                    message_id=_uuid(message_id),
                    thread_id=_uuid(thread_id),
                    script_key=key,
                ),
                failure_code=failure_code,
            )
        except Exception as exc:
            log.warning("script_record_failed", script_id=script_id, error=type(exc).__name__)
            return
        if outcome.status != "ok" or procedure_id is not None or not distinct:
            return
        try:
            await self._maybe_submit(agent, source, key, distinct, user_turn)
        except Exception as exc:
            log.warning("script_candidate_failed", script_key=key, error=type(exc).__name__)

    async def _maybe_submit(
        self,
        agent: str,
        source: str,
        key: str,
        distinct: list[str],
        user_turn: str | None,
    ) -> None:
        recent = await self._store.list_by_script_key(key, limit=_STREAK)
        if len(recent) < _STREAK or any(
            r.lifecycle is not ActionLifecycle.SUCCEEDED for r in recent
        ):
            return
        name = f"Script: {' → '.join(distinct)} [{key[:8]}]"[:_NAME_MAX]
        if await self._admission.candidate_exists(name):
            return
        trigger = (user_turn or "").strip()[:_TRIGGER_MAX] or f"repeat the {agent} read script"
        await self._admission.submit_procedure_candidate(
            ProcedureCandidate(
                source_kind=ProcedureSourceKind.TOOL_SCRIPT,
                provenance=Provenance.SYNTHESIZED,
                name=name,
                trigger=trigger,
                preconditions=[],
                steps=[source],
                success_criteria=["script ends ok"],
                limits=distinct,
                evidence_refs=[EvidenceRef(kind="action_record", id=r.id) for r in recent],
            )
        )
        log.info("script_candidate_submitted", script_key=key, name=name)
