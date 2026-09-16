from __future__ import annotations

import re

from ze_memory.procedures.store import ProcedureStore
from ze_memory.procedures.types import (
    IdentityStatus,
    MatchState,
    ProcedureMatch,
    ProcedureTaskContext,
    VersionStatus,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def intersect_tools(
    agent_allowed: frozenset[str],
    capability_allowed: frozenset[str],
    procedure_relevant: frozenset[str],
) -> frozenset[str]:
    narrowed = agent_allowed & capability_allowed
    if not procedure_relevant:
        return narrowed
    return narrowed & procedure_relevant


def _tokens(text: str) -> set[str]:
    return {part for part in _TOKEN_RE.findall(text.lower()) if len(part) > 2}


def _trigger_relevant(trigger: str, task_text: str) -> bool:
    tokens = _tokens(trigger)
    if not tokens:
        return False
    haystack = task_text.lower()
    hits = sum(1 for token in tokens if token in haystack)
    return hits >= max(1, (len(tokens) + 1) // 2)


def _precondition_satisfied(condition: str, facts: list[str]) -> bool:
    tokens = _tokens(condition)
    if not tokens:
        return True
    blob = " ".join(facts).lower()
    return all(token in blob for token in tokens)


class ProcedureDiscovery:
    def __init__(self, store: ProcedureStore) -> None:
        self._store = store

    async def match(
        self,
        context: ProcedureTaskContext,
        *,
        agent_allowed_tools: frozenset[str],
        capability_allowed_tools: frozenset[str],
    ) -> list[ProcedureMatch]:
        matches: list[ProcedureMatch] = []
        for version in await self._store.list_active_versions():
            if version.status is not VersionStatus.ACTIVE or version.id is None:
                continue
            identity = await self._store.get_identity(version.procedure_id)
            if identity is None or identity.status is not IdentityStatus.ACTIVE:
                continue
            relevant_tools = frozenset(version.limits)
            effective = intersect_tools(
                agent_allowed_tools, capability_allowed_tools, relevant_tools
            )
            if not _trigger_relevant(version.trigger, context.task_text):
                matches.append(
                    ProcedureMatch(
                        procedure_id=version.procedure_id,
                        version_id=version.id,
                        version_number=version.version_number,
                        name=version.name,
                        trigger=version.trigger,
                        steps=list(version.steps),
                        state=MatchState.NOT_RELEVANT,
                        matched_trigger="",
                        satisfied_preconditions=[],
                        unmet_preconditions=list(version.preconditions),
                        effective_tool_names=effective,
                        procedure_relevant_tools=relevant_tools,
                    )
                )
                continue
            satisfied = [
                item
                for item in version.preconditions
                if _precondition_satisfied(item, context.available_facts)
            ]
            unmet = [
                item for item in version.preconditions if item not in satisfied
            ]
            state = MatchState.BLOCKED if unmet else MatchState.READY
            matches.append(
                ProcedureMatch(
                    procedure_id=version.procedure_id,
                    version_id=version.id,
                    version_number=version.version_number,
                    name=version.name,
                    trigger=version.trigger,
                    steps=list(version.steps),
                    state=state,
                    matched_trigger=version.trigger,
                    satisfied_preconditions=satisfied,
                    unmet_preconditions=unmet,
                    effective_tool_names=effective,
                    procedure_relevant_tools=relevant_tools,
                )
            )
        return [
            match
            for match in matches
            if match.state in {MatchState.READY, MatchState.BLOCKED}
        ]


def format_procedure_guidance(matches: list[ProcedureMatch]) -> str | None:
    if not matches:
        return None
    lines = [
        "[Procedure guidance — advisory only. Call invoke_procedure before "
        "following steps. A match does not execute anything.]"
    ]
    for match in matches:
        lines.append(
            f"- [{match.state.value}] {match.name} v{match.version_number} "
            f"id={match.procedure_id}"
        )
        lines.append(f"  trigger: {match.matched_trigger or match.trigger}")
        if match.unmet_preconditions:
            lines.append(f"  unmet: {'; '.join(match.unmet_preconditions)}")
        if match.steps:
            lines.append(f"  steps: {'; '.join(list(match.steps)[:8])}")
    return "\n".join(lines)
