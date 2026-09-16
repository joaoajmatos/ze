from __future__ import annotations

from uuid import UUID

from ze_agents.claims import ClaimKind, Provenance
from ze_agents.tool import ToolAccess, tool
from ze_logging import get_logger
from ze_sdk.contribution import TargetFace
from ze_sdk.memory import (
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
    return {"ok": True, "id": str(fact.id)}


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Retract a stored fact the user asked Ze to forget. "
        "Pass a natural-language query or a predicate. "
        "Only confirm forgotten after ok is true."
    ),
)
async def forget_fact(query: str, memory_store: PostgresMemoryStore) -> dict:
    text = query.strip()
    if not text:
        return {"ok": False, "error": "query is required"}
    try:
        ids: list[UUID] = await memory_store._retract_facts_matching(text)
    except Exception as exc:
        log.warning("forget_fact_failed", query=text, error=str(exc))
        return {"ok": False, "error": str(exc)}
    if not ids:
        return {"ok": False, "error": "no matching fact"}
    return {"ok": True, "ids": [str(i) for i in ids]}
