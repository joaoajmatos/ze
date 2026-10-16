"""Graph turn helpers — builds state/config and interprets LangGraph outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ze_agents.interface.types import RawInput

from ze_agents.park import WriteConfirmation

if TYPE_CHECKING:
    from ze_core.container import Container

NO_PENDING_CONFIRMATION = "No pending confirmation."


def make_graph_input(
    raw: RawInput,
    session_id: str,
) -> dict:
    """Build AgentState input for the main conversation graph from raw transport input.

    ``session_id`` is the conversation identifier — the same string used as
    ``thread_id`` in LangGraph config and as ``sessions.id`` / ``messages.thread_id``
    on the API layer.

    ``messages`` and ``last_active_at`` are intentionally absent: LangGraph input
    keys overwrite checkpointed channel values, and those two must survive across
    turns so follow-ups keep conversation history (write_memory appends to them).
    """
    modality = "voice" if raw.audio else "image" if raw.image else "text"
    return {
        "prompt": raw.text or "",
        "session_id": session_id,
        "input_modality": modality,
        "audio_data": raw.audio,
        "audio_mime": raw.audio_mime,
        "image_data": raw.image,
        "image_mime": raw.image_mime,
        "image_caption": None,
        "envelope": None,
        "memory_context": None,
        "agent_context": None,
        "agent_result": None,
        "subtask_results": [],
        "completed_subtask_indexes": [],
        "blocked": False,
        "budget_status": None,
        "budget_approved": False,
        "parked_subtasks": [],
        "write_confirmation": None,
        "write_decisions": [],
        "write_rounds": 0,
        "write_outcomes": [],
        "final_response": None,
        "error": None,
        "components": [],
        "conductor_hint": None,
        "conductor_ledger": [],
        "conductor_delegate_counts": {},
        "conductor_delegate_total": 0,
        "routing_hints": None,
        "correlations": [],
        "message_trace": None,
        "judgments": [],
        "skill_matches": None,
    }


def make_graph_input_from_raw_text(prompt: str, session_id: str) -> dict:
    return make_graph_input(RawInput(text=prompt), session_id)


def extract_response(state: dict) -> str:
    """Return the best available response text from a completed graph state."""
    if state.get("final_response"):
        return state["final_response"]
    result = state.get("agent_result")
    if result and result.response:
        return result.response
    return ""


@dataclass
class TurnResult:
    """Outcome of one main-graph invocation (may pause for the user's confirmation)."""

    final_state: dict
    config: dict
    interrupted: bool
    confirmation: WriteConfirmation | None = None
    error: str | None = None
    response: str | None = None
    message_id: str = ""


def open_confirmation(graph_state_obj: Any) -> WriteConfirmation | None:
    """The confirmation a paused graph is waiting on, if any."""
    if graph_state_obj is None:
        return None
    candidates: list[Any] = list(getattr(graph_state_obj, "interrupts", None) or ())
    for task in getattr(graph_state_obj, "tasks", None) or ():
        candidates.extend(getattr(task, "interrupts", None) or ())
    for item in candidates:
        value = getattr(item, "value", item)
        if isinstance(value, WriteConfirmation):
            return value
    return None


async def invoke_raw_turn(
    container: Container,
    thread_id: str,
    raw: RawInput,
    *,
    config_extra: dict | None = None,
) -> TurnResult:
    """Run the conversation graph once from raw transport input and interpret the outcome."""
    from uuid import uuid4
    from ze_core.orchestration.nodes.trace import _extract_memory_chunks

    graph_input = make_graph_input(raw, thread_id)
    config = container._build_config(thread_id, **(config_extra or {}))
    interface = container.interface
    graph_name = getattr(container.graph, "name", "LangGraph")
    pending_message_id = str(uuid4())

    final_state: dict = {}
    graph_ended = False

    async for event in container.graph.astream_events(
        graph_input, config, version="v2"
    ):
        kind = event["event"]
        name = event.get("name", "")
        data = event.get("data", {})

        if kind == "on_chain_end" and name == "embed_route":
            env = (data.get("output") or {}).get("envelope")
            if env is not None and interface is not None:
                await interface.send_trace_partial(
                    pending_message_id,
                    {
                        "agent": env.primary_agent,
                        "routing_method": env.routing_method,
                        "confidence": env.confidence,
                        "score_gap": env.score_gap,
                        "is_compound": env.is_compound,
                        "subtasks": [s.agent for s in env.subtasks]
                        if env.is_compound
                        else [],
                    },
                    thread_id,
                )

        elif kind == "on_chain_end" and name == "fetch_context":
            memory_ctx = (data.get("output") or {}).get("memory_context")
            if memory_ctx is not None and interface is not None:
                chunks = _extract_memory_chunks(memory_ctx)
                if chunks:
                    await interface.send_trace_partial(
                        pending_message_id,
                        {
                            "memory_chunks": [
                                {"text": c.text, "score": c.score, "source": c.source}
                                for c in chunks
                            ],
                        },
                        thread_id,
                    )

        elif kind == "on_tool_end":
            if interface is not None:
                output = data.get("output")
                content = (
                    getattr(output, "content", None) if output is not None else None
                )
                if content is None and output is not None:
                    content = str(output)
                snippet = str(content)[:200] if content else ""
                await interface.send_trace_partial(
                    pending_message_id,
                    {
                        "tool_calls": [
                            {
                                "name": name,
                                "result_snippet": snippet,
                                "duration_ms": 0,
                                "success": True,
                            }
                        ],
                    },
                    thread_id,
                )

        elif kind == "on_chain_end" and name == graph_name:
            final_state = data.get("output") or {}
            graph_ended = True

    graph_state_obj = await container.graph.aget_state(config)
    interrupted = bool(graph_state_obj.next) if graph_state_obj else False
    if not graph_ended and graph_state_obj:
        final_state = graph_state_obj.values

    return TurnResult(
        final_state=final_state,
        config=config,
        interrupted=interrupted,
        confirmation=open_confirmation(graph_state_obj),
        error=final_state.get("error"),
        response=None if interrupted else extract_response(final_state),
        message_id=pending_message_id,
    )


async def resume_turn(
    container: Container, config: dict, resume: Any = None
) -> TurnResult:
    """Resume the graph after the user answers its open confirmation."""
    from langgraph.types import Command

    graph_state_obj = await container.graph.aget_state(config)
    if open_confirmation(graph_state_obj) is None:
        return TurnResult(
            final_state={},
            config=config,
            interrupted=False,
            error=NO_PENDING_CONFIRMATION,
        )
    value = resume if resume is not None else {"choice": "approve"}
    final_state = await container.graph.ainvoke(Command(resume=value), config)
    new_state = await container.graph.aget_state(config)
    if new_state and new_state.next:
        return TurnResult(
            final_state=new_state.values or final_state,
            config=config,
            interrupted=True,
            confirmation=open_confirmation(new_state),
            error=(new_state.values or {}).get("error") if new_state.values else None,
            response=None,
        )
    return TurnResult(
        final_state=final_state,
        config=config,
        interrupted=False,
        error=final_state.get("error") if isinstance(final_state, dict) else None,
        response=extract_response(final_state) if isinstance(final_state, dict) else "",
    )


async def invoke_retry_turn(
    container: Container,
    thread_id: str,
    user_text: str,
    *,
    config_extra: dict | None = None,
) -> TurnResult:
    """Regenerate the latest reply for `user_text` with WRITE tools blocked.

    Rewinds the thread's checkpointed history past the original exchange, runs the
    graph in ``retry_mode``, and puts the history back if the run does not produce
    a plain reply. The caller must hold the thread's turn lock.
    """
    from ze_agents.errors import RetryFailedError
    from ze_core.conversation.rewind import restore_messages, rewind_last_exchange

    extra = {**(config_extra or {}), "retry_mode": True}
    config = container._build_config(thread_id, **extra)
    original = await rewind_last_exchange(container.graph, config)
    try:
        result = await invoke_raw_turn(
            container, thread_id, RawInput(text=user_text), config_extra=extra
        )
    except Exception as exc:
        await restore_messages(container.graph, config, original)
        raise RetryFailedError(str(exc)) from exc
    if result.interrupted or result.error or not result.response:
        await restore_messages(container.graph, config, original)
        raise RetryFailedError(
            result.error
            or (
                "retry paused for confirmation" if result.interrupted else "empty reply"
            )
        )
    return result
