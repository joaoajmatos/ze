"""Runs a workflow graph unattended and holds it when a step needs approval (Phase 181)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from ze_agents.park import WriteConfirmation
from ze_automation.holds.resumer import open_hold
from ze_automation.holds.store import HeldWriteStore
from ze_automation.holds.types import HeldWrite, HeldWriteStatus
from ze_automation.workflow.scheduler import WorkflowScheduler
from ze_automation.workflow.store import WorkflowStore
from ze_automation.workflow.types import Workflow
from ze_automation.workspace_unattended import unattended_workspace
from ze_logging import get_logger

log = get_logger(__name__)


def open_confirmation(snapshot: Any) -> WriteConfirmation | None:
    """The write confirmation a paused graph is waiting on, if any."""
    if snapshot is None or not getattr(snapshot, "next", None):
        return None
    candidates: list[Any] = list(getattr(snapshot, "interrupts", None) or ())
    for task in getattr(snapshot, "tasks", None) or ():
        candidates.extend(getattr(task, "interrupts", None) or ())
    for item in candidates:
        value = getattr(item, "value", item)
        if isinstance(value, WriteConfirmation):
            return value
    return None


class WorkflowRunner:
    """Drives one workflow execution through the compiled graph.

    When the graph pauses at `await_write_confirmation` the run is held, not failed:
    a `held_writes` row is opened, the execution goes to `held`, and one push asks
    the user. `resume` continues the same checkpointed thread after the answer.
    """

    def __init__(
        self,
        *,
        scheduler: WorkflowScheduler,
        graph: Any,
        configurable: dict[str, Any],
        workflow_store: WorkflowStore,
        held_store: HeldWriteStore,
        notifier: Any,
        workspace_gate: Any = None,
    ) -> None:
        self._graph = graph
        self._configurable = configurable
        self._workflows = workflow_store
        self._held = held_store
        self._notifier = notifier
        self._gate = workspace_gate
        self._scheduler = scheduler

    def _config(self, execution_id: UUID) -> dict[str, Any]:
        return {
            "configurable": {
                **self._configurable,
                "thread_id": str(execution_id),
                "workflow_store": self._workflows,
            }
        }

    async def run(
        self, workflow: Workflow, execution_id: UUID, graph_input: Any
    ) -> None:
        config = self._config(execution_id)
        async with unattended_workspace(self._gate):
            await self._graph.ainvoke(graph_input, config)
        confirmation = open_confirmation(await self._graph.aget_state(config))
        if confirmation is None:
            return
        await self._workflows.set_execution_status(execution_id, "held")
        await open_hold(
            held_store=self._held,
            notify=self._notifier.notify,
            source="workflow",
            owner_ref=str(execution_id),
            source_name=f"Workflow '{workflow.name}'",
            confirmation=confirmation,
            payload={
                "workflow_id": str(workflow.id),
                "execution_id": str(execution_id),
            },
        )

    async def resume(self, hold: HeldWrite, choice: str, edits: dict[str, str]) -> None:
        from langgraph.types import Command

        execution_id = UUID(hold.payload["execution_id"])
        workflow = await self._workflows.get(UUID(hold.payload["workflow_id"]))
        if workflow is None:
            await self._workflows.finish_execution(
                execution_id, "failed", error="Workflow was deleted while held"
            )
            return
        if not await self._workflows.set_execution_status(
            execution_id, "running", expected="held"
        ):
            log.info("held_workflow_not_held", execution_id=str(execution_id))
            return
        resume_input = Command(resume={"choice": choice, "edits": edits})

        async def _continue(wf: Workflow, exec_id: UUID) -> None:
            await self.run(wf, exec_id, resume_input)

        await self._scheduler.resume_execution(workflow, execution_id, _continue)

    async def cancel_held(self, execution_id: UUID) -> None:
        """Cancel a held run: deny its open hold so a later answer cannot resume it.

        An answer that already claimed the hold wins: the run resumes, not cancels.
        """
        claimed = False
        for hold in await self._held.list(HeldWriteStatus.OPEN):
            if hold.source == "workflow" and hold.owner_ref == str(execution_id):
                claimed = await self._held.decide(
                    hold.request_id, HeldWriteStatus.DENIED
                )
        if claimed:
            await self._workflows.finish_execution(execution_id, "cancelled")
