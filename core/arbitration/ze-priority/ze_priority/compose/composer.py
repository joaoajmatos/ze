from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from ze_automation.goals.store import GoalStore
from ze_automation.holds.store import HeldWriteStore
from ze_automation.holds.types import HeldWriteStatus
from ze_automation.workflow.store import WorkflowStore
from ze_components.serialize import serialize_primitive
from ze_logging import get_logger
from ze_worldstate.store import LoopStore
from ze_worldstate.types import LoopState

from ze_priority.compose import rules
from ze_priority.compose.types import (
    Composition,
    Draft,
    SourceSnapshot,
    WorkflowDigest,
)
from ze_priority.view import PriorityView

log = get_logger(__name__)

_OPEN_STATES = [
    LoopState.SUSPECTED.value,
    LoopState.ACTIVE.value,
    LoopState.DRIFTING.value,
]


class WorldComposer:
    """Builds the three composed answers from the stores. Reads only; posture comes from the records."""

    def __init__(
        self,
        priority_view: PriorityView,
        loop_store: LoopStore,
        goal_store: GoalStore,
        workflow_store: WorkflowStore,
        held_write_store: HeldWriteStore,
        embedder: Any = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._priority_view = priority_view
        self._loop_store = loop_store
        self._goal_store = goal_store
        self._workflow_store = workflow_store
        self._held_write_store = held_write_store
        self._embedder = embedder
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def compose_slipping(self) -> Composition:
        now = self._clock()
        snapshot = await self._read(priority=True, loops=True, goals=True)
        return self._finish(rules.slipping(snapshot, now))

    async def compose_decisions(self) -> Composition:
        now = self._clock()
        snapshot = await self._read(loops=True, goals=True, held_writes=True)
        return self._finish(rules.decisions(snapshot, now))

    async def compose_topic(self, topic: str) -> Composition:
        now = self._clock()
        snapshot = await self._read(priority=True, loops=True, goals=True)
        snapshot.workflows = await self._matched_workflows(topic, snapshot)
        return self._finish(rules.topic(snapshot, topic, self._embedder, now))

    def _finish(self, draft: Draft) -> Composition:
        return Composition(
            headline=draft.headline,
            components=[serialize_primitive(c) for c in draft.components],
            summary=draft.summary,
            sources_failed=draft.sources_failed,
        )

    async def _read(
        self,
        *,
        priority: bool = False,
        loops: bool = False,
        goals: bool = False,
        held_writes: bool = False,
    ) -> SourceSnapshot:
        wanted: dict[str, Awaitable[Any]] = {}
        if priority:
            wanted["priority"] = self._priority_view.rank()
        if loops:
            wanted["loops"] = self._loop_store.list(_OPEN_STATES)
        if goals:
            wanted["goals"] = self._goal_store.list_progress()
        if held_writes:
            wanted["held_writes"] = self._held_write_store.list(HeldWriteStatus.OPEN)

        results = await asyncio.gather(*wanted.values(), return_exceptions=True)
        snapshot = SourceSnapshot()
        for name, result in zip(wanted, results):
            if isinstance(result, BaseException):
                log.warning("compose_source_failed", source=name, error=str(result))
                snapshot.failed.add(name)
                continue
            if name == "priority":
                snapshot.ranking = result
                snapshot.failed |= set(result.sources_failed)
            else:
                setattr(snapshot, name, result)
        return snapshot

    async def _matched_workflows(
        self, topic: str, snapshot: SourceSnapshot
    ) -> list[WorkflowDigest] | None:
        try:
            workflows = await self._workflow_store.list_all()
            matched = rules.match_workflows(workflows, topic, self._embedder)
            executions = await asyncio.gather(
                *(self._workflow_store.list_executions(w.id, limit=1) for w in matched)
            )
        except Exception as exc:
            log.warning("compose_source_failed", source="workflows", error=str(exc))
            snapshot.failed.add("workflows")
            return None
        return [
            WorkflowDigest(workflow, runs[0] if runs else None)
            for workflow, runs in zip(matched, executions)
        ]
