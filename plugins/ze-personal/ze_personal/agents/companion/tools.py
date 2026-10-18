from __future__ import annotations

from uuid import UUID

from ze_agents.claims import ClaimKind, Provenance
from ze_agents.tool import Injected, ToolAccess, tool
from ze_sdk import ToolReversibility, undo_payload
from ze_logging import get_logger
from ze_sdk.contribution import TargetFace
from ze_sdk.proactive import NotificationStore
from ze_sdk.memory import (
    FactRestoreConflictError,
    Fact,
    PerceptionFactSubmit,
    PostgresMemoryStore,
    submit_perception_facts,
)

log = get_logger(__name__)


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Persist a durable fact the user asked Ze to remember. "
        "Use snake_case predicate (preference, identity, constraint, "
        "relationship, contact_detail, or a specific label). "
        "Only confirm to the user after ok is true."
    ),
    reversibility=ToolReversibility.REVERSIBLE,
    undo_tool="forget_fact",
    undo_note="Does not remove copies already used in earlier replies",
    effect_phrase="saved something to memory",
)
async def remember_fact(
    predicate: str,
    value: str,
    memory_store: PostgresMemoryStore,
) -> dict:
    pred = predicate.strip()
    val = value.strip()
    if not pred or not val:
        return {"ok": False, "error": "predicate and value are required"}
    fact = Fact(
        predicate=pred,
        value=val,
        confidence=0.95,
        reviewed=True,
        provenance=Provenance.PROMPT_SUPPLIED,
        claim_kind=ClaimKind.FACT,
        agent="companion",
    )
    try:
        await submit_perception_facts(
            memory_store,
            [
                PerceptionFactSubmit(
                    fact=fact,
                    provenance=Provenance.PROMPT_SUPPLIED,
                    target_face=TargetFace.USER,
                    evidence=[],
                )
            ],
        )
    except Exception as exc:
        log.warning("remember_fact_failed", predicate=pred, error=str(exc))
        return {"ok": False, "error": str(exc)}
    if fact.id is None:
        return {"ok": False, "error": "memory write returned no id"}
    return {
        "ok": True,
        "id": str(fact.id),
        "undo": undo_payload(
            fact_id=str(fact.id),
            restore_fact_ids=[str(i) for i in fact.displaced_ids],
        ),
    }


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Retract a stored fact the user asked Ze to forget. "
        "Pass a natural-language query or a predicate. "
        "fact_id and restore_fact_ids are only for rolling back a remembered "
        "fact; never set them. "
        "Only confirm forgotten after ok is true."
    ),
    reversibility=ToolReversibility.IRREVERSIBLE,
    effect_phrase="forgot a memory",
)
async def forget_fact(
    memory_store: PostgresMemoryStore,
    query: str = "",
    fact_id: str = "",
    restore_fact_ids: Injected[list[str] | None] = None,
) -> dict:
    text = query.strip()
    target = fact_id.strip()
    if bool(text) == bool(target):
        return {"ok": False, "error": "pass exactly one of query or fact_id"}
    if target:
        try:
            fid = UUID(target)
            restore = [UUID(r) for r in restore_fact_ids or []]
            await memory_store.retract_fact_and_restore(fid, restore)
        except (FactRestoreConflictError, ValueError) as exc:
            log.warning("forget_fact_restore_failed", fact_id=target, error=str(exc))
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "ids": [target],
            "restored": [str(r) for r in restore],
        }
    try:
        ids: list[UUID] = await memory_store._retract_facts_matching(text)
    except Exception as exc:
        log.warning("forget_fact_failed", query=text, error=str(exc))
        return {"ok": False, "error": str(exc)}
    if not ids:
        return {"ok": False, "error": "no matching fact"}
    return {"ok": True, "ids": [str(i) for i in ids]}


_BRIEFING_EVENT = "morning_brief"


@tool(
    access=ToolAccess.READ,
    description=(
        "Read the morning briefings Ze actually sent, newest first: when each was "
        "sent, whether it was delivered or held, whether it was marked read in the notification centre, and "
        "the full text of what it covered. Use for any question about a briefing "
        "Ze already sent. count is how many to return (1-5)."
    ),
)
async def get_briefing(notification_store: NotificationStore, count: int = 1) -> dict:
    limit = max(1, min(count, 5))
    try:
        rows = await notification_store.latest_by_event(_BRIEFING_EVENT, limit=limit)
    except Exception as exc:
        log.warning("get_briefing_failed", error=str(exc))
        return {"found": False, "error": f"could not read the briefing record: {exc}"}
    return {
        "found": bool(rows),
        "briefings": [
            {
                "sent_at": r.delivered_at.isoformat() if r.delivered_at else None,
                "created_at": r.created_at.isoformat(),
                "delivery": r.delivery,
                "marked_read": r.read_at is not None,
                "marked_read_at": r.read_at.isoformat() if r.read_at else None,
                "delivery_status": (
                    f"delivered at {r.delivered_at.isoformat()}"
                    if r.delivered_at
                    else "not confirmed as delivered"
                ),
                "body": r.body,
            }
            for r in rows
        ],
    }
