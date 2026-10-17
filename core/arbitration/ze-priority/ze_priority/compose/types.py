from __future__ import annotations

from dataclasses import dataclass, field

from ze_automation.goals.types import GoalProgress
from ze_automation.holds.types import HeldWrite
from ze_automation.workflow.types import Workflow, WorkflowExecution
from ze_worldstate.types import OpenLoop

from ze_priority.types import PriorityRanking


@dataclass
class WorkflowDigest:
    workflow: Workflow
    last_execution: WorkflowExecution | None


@dataclass
class SourceSnapshot:
    """Records fetched for one composition. A source that failed is `None` and named in `failed`."""

    ranking: PriorityRanking | None = None
    loops: list[OpenLoop] | None = None
    goals: list[GoalProgress] | None = None
    held_writes: list[HeldWrite] | None = None
    workflows: list[WorkflowDigest] | None = None
    failed: set[str] = field(default_factory=set)


@dataclass
class Draft:
    """A composition before serialization: primitive dataclasses, not wire dicts."""

    headline: str
    components: list[object]
    summary: str
    sources_failed: list[str] = field(default_factory=list)


@dataclass
class Composition:
    headline: str
    components: list[dict]
    summary: str
    sources_failed: list[str] = field(default_factory=list)
