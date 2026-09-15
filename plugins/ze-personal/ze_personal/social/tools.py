"""Conversational surfaces for co-occurrence inference (Phase 130).

`who_is_on_project` never blends confirmed graph membership with hedged,
unconfirmed inference into one undifferentiated list (FR-005/FR-011) —
callers render `confirmed_members` without hedging language and
`hedged_candidates` with it.
"""

from __future__ import annotations

import time
from uuid import UUID

from ze_agents.tool import ToolAccess, tool
from ze_agents.types import ToolCall
from ze_logging import get_logger
from ze_memory.graph.predicates import WORKS_ON
from ze_proactive.staleness import is_stale

from ze_personal.social.promotion import promote_hypothesis
from ze_personal.social.scoring import RECENCY_WINDOW_DAYS

log = get_logger(__name__)


@tool(
    access=ToolAccess.READ,
    description=(
        "Answer 'who is on project X' — confirmed graph members and hedged, "
        "unconfirmed candidates are returned separately and must never be "
        "presented as one undifferentiated list."
    ),
)
async def who_is_on_project(
    project_name: str,
    memory_store: object,
    hypothesis_store: object,
) -> ToolCall:
    args = {"project_name": project_name}
    start = time.monotonic()
    try:
        project = await memory_store.find_entity_by_name(project_name, entity_type="project")  # type: ignore[attr-defined]
        confirmed_members: list[str] = []
        hedged_candidates: list[dict] = []

        if project is not None:
            graph_store = getattr(memory_store, "graph_store", None)
            if graph_store is not None:
                edges = await graph_store.list_relationships_by_target(
                    [project.id], predicates=[WORKS_ON]
                )
                for edge in edges:
                    if edge.last_contact is not None and not is_stale(
                        edge.last_contact, RECENCY_WINDOW_DAYS
                    ):
                        person = await memory_store.get_entity(edge.source_id)  # type: ignore[attr-defined]
                        if person is not None:
                            confirmed_members.append(person.canonical_name)

            hypotheses = await hypothesis_store.list_by_entities([project.id])  # type: ignore[attr-defined]
            for h in hypotheses:
                if h.promoted_at is not None:
                    continue
                other_ids = [e for e in h.entities if e != project.id]
                for person_id in other_ids:
                    person = await memory_store.get_entity(person_id)  # type: ignore[attr-defined]
                    if person is None:
                        continue
                    hedged_candidates.append(
                        {
                            "person_name": person.canonical_name,
                            "evidence_summaries": [ev.label for ev in h.evidence],
                        }
                    )

        result = {
            "project_name": project_name,
            "confirmed_members": confirmed_members,
            "hedged_candidates": hedged_candidates,
        }
        return ToolCall(
            tool_name="who_is_on_project",
            args=args,
            result=result,
            duration_ms=int((time.monotonic() - start) * 1000),
            success=True,
        )
    except Exception as exc:
        log.warning("who_is_on_project_failed", error=str(exc))
        return ToolCall(
            tool_name="who_is_on_project",
            args=args,
            result={"confirmed_members": [], "hedged_candidates": []},
            duration_ms=int((time.monotonic() - start) * 1000),
            success=False,
            error=str(exc),
        )


@tool(
    access=ToolAccess.WRITE,
    description=(
        "User explicitly confirms a co-occurrence inference (e.g. 'yes, Alice "
        "is on Launch') — marks it confirmed and promotes it to a real graph "
        "edge immediately, regardless of corroboration."
    ),
)
async def confirm_project_membership(
    hypothesis_id: str,
    hypothesis_store: object,
    memory_store: object,
    collision_store: object = None,
    nli_client: object = None,
) -> ToolCall:
    args = {"hypothesis_id": hypothesis_id}
    start = time.monotonic()
    try:
        hid = UUID(hypothesis_id)
        hypothesis = await hypothesis_store.confirm(hid)  # type: ignore[attr-defined]
        await promote_hypothesis(
            hypothesis,
            hypothesis_store=hypothesis_store,
            memory_store=memory_store,
            collision_store=collision_store,
            nli_client=nli_client,
        )
        return ToolCall(
            tool_name="confirm_project_membership",
            args=args,
            result={"confirmed": True, "hypothesis_id": hypothesis_id},
            duration_ms=int((time.monotonic() - start) * 1000),
            success=True,
        )
    except Exception as exc:
        log.warning("confirm_project_membership_failed", error=str(exc))
        return ToolCall(
            tool_name="confirm_project_membership",
            args=args,
            result={"confirmed": False},
            duration_ms=int((time.monotonic() - start) * 1000),
            success=False,
            error=str(exc),
        )
