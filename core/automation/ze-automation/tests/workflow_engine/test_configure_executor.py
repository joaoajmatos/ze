from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from ze_automation.bootstrap import configure_workflow_executor


async def test_executor_starts_from_the_injected_turn_input() -> None:
    stack = MagicMock()
    stack.workflow_scheduler = MagicMock()
    stack.held_write_resumer = MagicMock()
    begin_workflow_turn = MagicMock(
        return_value={"messages": ["seed"], "session_id": "s"}
    )
    step = SimpleNamespace(id="s1")
    workflow = SimpleNamespace(id=uuid4(), name="Digest", steps=[step])
    execution_id = uuid4()

    with patch("ze_automation.bootstrap.WorkflowRunner") as runner_cls:
        runner_cls.return_value.run = AsyncMock()
        await configure_workflow_executor(
            stack,
            SimpleNamespace(memory_store=None, openrouter_client=None, embedder=None),
            [],
            settings=MagicMock(),
            notifier=MagicMock(),
            checkpointer=None,
            router=None,
            persona_store=None,
            workflow_graph_builder=MagicMock(),
            begin_workflow_turn=begin_workflow_turn,
        )
        executor = stack.workflow_scheduler.configure_executor.call_args.kwargs[
            "executor"
        ]
        await executor(workflow, execution_id)

    begin_workflow_turn.assert_called_once_with(workflow)
    _, run_execution_id, state = runner_cls.return_value.run.call_args.args
    assert run_execution_id == execution_id
    assert state["messages"] == ["seed"]
    assert state["workflow_id"] == workflow.id
    assert state["workflow_execution_id"] == execution_id
    assert state["current_step_id"] == "s1"
    assert state["workflow_step_results"] == []
