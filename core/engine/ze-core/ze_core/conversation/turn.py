"""Graph turn helpers — builds state/config and interprets LangGraph outcomes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from ze_agents.interface.types import RawInput

from ze_agents.lifetime import turn_reset
from ze_agents.park import WriteConfirmation
from ze_agents.types import AbortToken
from ze_logging import get_logger
from ze_core.orchestration.nodes.trace import ROUTING_SCORES_SHOWN
from ze_core.orchestration.state import AgentState
from ze_core.telemetry.context import enter_turn_context
from ze_core.telemetry.turn import (
    TurnTelemetry,
    TurnTelemetryRegistry,
    current_turn_telemetry,
    monotonic,
)

log = get_logger(__name__)

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
    modality = "voice" if raw.voice else "image" if raw.image else "text"
    return {
        **turn_reset(AgentState),
        "prompt": raw.text or "",
        "session_id": session_id,
        "input_modality": modality,
        "voice_input": (
            {"duration_s": raw.voice.duration_s, "edited": raw.voice.edited}
            if raw.voice
            else None
        ),
        "image_data": raw.image,
        "image_mime": raw.image_mime,
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


def turn_has_reply(outcome: Any) -> bool:
    """True when a turn produced text or rendered components for the user.

    Every entry point that delivers a turn asks this, so a reply that is only
    components is never mistaken for an empty one.
    """
    if getattr(outcome, "response", None):
        return True
    state = getattr(outcome, "final_state", None)
    return isinstance(state, dict) and bool(state.get("components"))


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

    @property
    def has_reply(self) -> bool:
        return turn_has_reply(self)


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


def _main_model(final_state: dict, config: dict) -> str | None:
    """The model that wrote the reply: the tier's, else the routed agent's; compound
    turns use the synthesis model."""
    try:
        envelope = final_state.get("envelope")
        if envelope is not None and getattr(envelope, "is_compound", False):
            from ze_agents.defaults import MODEL_SYNTHESIS
            from ze_agents.model_resolution import resolve_model

            cfg = config.get("configurable", {}).get("settings")
            app_config = (
                cfg if isinstance(cfg, dict) else getattr(cfg, "config", None) or {}
            )
            return resolve_model("synthesis", MODEL_SYNTHESIS, app_config)
        tier = final_state.get("tier")
        if tier is not None and getattr(tier, "model", None):
            return tier.model
        ctx = final_state.get("agent_context")
        return getattr(ctx, "model", None)
    except Exception:
        return None


def _registry(container: Any) -> TurnTelemetryRegistry | None:
    """The container's recorder registry; test doubles without one run untimed."""
    registry = getattr(container, "turn_telemetry", None)
    return registry if isinstance(registry, TurnTelemetryRegistry) else None


async def _close(
    registry: TurnTelemetryRegistry, telemetry: TurnTelemetry | None, thread_id: str
) -> None:
    if telemetry is not None:
        await telemetry.close()
    registry.finish(thread_id)


async def _stamp_telemetry(
    telemetry: TurnTelemetry, final_state: dict, config: dict
) -> None:
    """Stamp the turn's measurements onto the committed trace, after the queued stage
    frames are out so none can arrive after the committed trace."""
    trace = final_state.get("message_trace") if isinstance(final_state, dict) else None
    await telemetry.drain()
    if trace is None:
        return
    final_state["message_trace"] = telemetry.stamp(
        trace, _main_model(final_state, config)
    )


def _routing_fields(env: Any) -> dict[str, Any]:
    scores = sorted((env.raw_scores or {}).items(), key=lambda kv: kv[1], reverse=True)[
        :ROUTING_SCORES_SHOWN
    ]
    if len(scores) < 2:
        scores = []  # a forced or single-score envelope has no shortlist to draw
    return {
        "routing_scores": [{"agent": a, "score": v} for a, v in scores],
        "routing_thresholds": {
            "threshold": env.threshold,
            "gap": env.gap_threshold,
        },
    }


def _tool_sink(telemetry: TurnTelemetry) -> Callable[[Any], None]:
    """The callable `call_tool` hands every finished ToolCall to: it enqueues one
    live tool row and returns at once."""

    def sink(call: Any) -> None:
        try:
            offset = None
            started = getattr(call, "started_at", None)
            if started is not None and not telemetry.partial:
                ms = round((started - telemetry.started) * 1000)
                if 0 <= ms <= round((monotonic() - telemetry.started) * 1000):
                    offset = ms
            result = getattr(call, "result", "") or ""
            telemetry.emit(
                {
                    "tool_calls": [
                        {
                            "call_id": call.call_id,
                            "name": call.tool_name,
                            "agent": getattr(call, "agent", None),
                            "gate": getattr(call, "gate", "none"),
                            "start_offset_ms": offset,
                            "duration_ms": call.duration_ms,
                            "success": call.success,
                            "result_snippet": str(result)[:200] if result else "",
                        }
                    ]
                }
            )
        except Exception as exc:
            log.warning("turn_telemetry_failed", method="tool_sink", error=str(exc))

    return sink


def _with_tool_sink(config: dict, telemetry: TurnTelemetry | None) -> dict:
    if telemetry is None:
        return config
    configurable = {
        **config.get("configurable", {}),
        "tool_sink": _tool_sink(telemetry),
    }
    return {**config, "configurable": configurable}


def _register_abort_token(container: Any, thread_id: str, token: AbortToken) -> None:
    """Let ``container.abort_invocation`` reach this turn; test doubles without a map run uncancellable."""
    tokens = getattr(container, "_abort_tokens", None)
    if tokens is not None:
        tokens[thread_id] = token


def _release_abort_token(container: Any, thread_id: str, token: AbortToken) -> None:
    """Drop the registration unless a newer turn on the thread has replaced it."""
    tokens = getattr(container, "_abort_tokens", None)
    if tokens is not None and tokens.get(thread_id) is token:
        del tokens[thread_id]


async def invoke_raw_turn(
    container: Container,
    thread_id: str,
    raw: RawInput,
    *,
    config_extra: dict | None = None,
) -> TurnResult:
    """Run the conversation graph once from raw transport input and interpret the outcome."""
    from uuid import uuid4
    from ze_core.conversation.messages.memory_chunks import extract_memory_chunks

    enter_turn_context(thread_id)
    graph_input = make_graph_input(raw, thread_id)
    abort_token = AbortToken()
    config = container._build_config(
        thread_id, **{**(config_extra or {}), "abort_token": abort_token}
    )
    interface = container.interface
    graph_name = getattr(container.graph, "name", "LangGraph")
    pending_message_id = str(uuid4())

    registry = _registry(container)
    telemetry = registry.start(thread_id) if registry is not None else None
    if telemetry is not None and interface is not None:
        telemetry.set_send(
            lambda fields: interface.send_trace_partial(
                pending_message_id, fields, thread_id
            )
        )
    config = _with_tool_sink(config, telemetry)
    token = current_turn_telemetry.set(telemetry)
    _register_abort_token(container, thread_id, abort_token)
    interrupted = False
    try:
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
                            **_routing_fields(env),
                        },
                        thread_id,
                    )

            elif kind == "on_chain_end" and name == "resolve_screen":
                screen = (data.get("output") or {}).get("screen_trace")
                if screen is not None and interface is not None:
                    await interface.send_trace_partial(
                        pending_message_id, {"screen": screen}, thread_id
                    )

            elif kind == "on_chain_end" and name == "choose_tier":
                tier = (data.get("output") or {}).get("tier")
                if tier is not None and interface is not None:
                    await interface.send_trace_partial(
                        pending_message_id, {"tier": asdict(tier)}, thread_id
                    )

            elif kind == "on_chain_end" and name == "fetch_context":
                memory_ctx = (data.get("output") or {}).get("memory_context")
                if memory_ctx is not None and interface is not None:
                    chunks = extract_memory_chunks(memory_ctx)
                    if chunks:
                        await interface.send_trace_partial(
                            pending_message_id,
                            {
                                "memory_chunks": [
                                    {
                                        "text": c.text,
                                        "score": c.score,
                                        "source": c.source,
                                        "extraction_confidence": c.extraction_confidence,
                                    }
                                    for c in chunks
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

        if telemetry is not None:
            if interrupted:
                telemetry.pause()
            else:
                await _stamp_telemetry(telemetry, final_state, config)
        return TurnResult(
            final_state=final_state,
            config=config,
            interrupted=interrupted,
            confirmation=open_confirmation(graph_state_obj),
            error=final_state.get("error"),
            response=None if interrupted else extract_response(final_state),
            message_id=pending_message_id,
        )
    finally:
        _release_abort_token(container, thread_id, abort_token)
        current_turn_telemetry.reset(token)
        if registry is not None and not interrupted:
            await _close(registry, telemetry, thread_id)


async def resume_turn(
    container: Container,
    config: dict,
    resume: Any = None,
    *,
    request_id: str | None = None,
) -> TurnResult:
    """Resume the graph after the user answers its open confirmation.

    With `request_id`, only the confirmation of that id is answered: an answer to a
    superseded confirmation never resumes the one that replaced it.
    """
    from langgraph.types import Command

    enter_turn_context(config["configurable"]["thread_id"])
    graph_state_obj = await container.graph.aget_state(config)
    confirmation = open_confirmation(graph_state_obj)
    if confirmation is None or (
        request_id is not None and confirmation.request_id != request_id
    ):
        registry = _registry(container)
        if confirmation is None and registry is not None:
            registry.finish(config["configurable"]["thread_id"])
        return TurnResult(
            final_state={},
            config=config,
            interrupted=False,
            error=NO_PENDING_CONFIRMATION,
        )
    value = resume if resume is not None else {"choice": "approve"}
    thread_id = config["configurable"]["thread_id"]
    registry = _registry(container)
    telemetry = registry.resume(thread_id) if registry is not None else None
    abort_token = AbortToken()
    config = {
        **config,
        "configurable": {**config["configurable"], "abort_token": abort_token},
    }
    config = _with_tool_sink(config, telemetry)
    token = current_turn_telemetry.set(telemetry)
    _register_abort_token(container, thread_id, abort_token)
    interrupted = False
    try:
        final_state = await container.graph.ainvoke(Command(resume=value), config)
        new_state = await container.graph.aget_state(config)
        if new_state and new_state.next:
            interrupted = True
            if telemetry is not None:
                telemetry.pause()
            return TurnResult(
                final_state=new_state.values or final_state,
                config=config,
                interrupted=True,
                confirmation=open_confirmation(new_state),
                error=(new_state.values or {}).get("error")
                if new_state.values
                else None,
                response=None,
            )
        if telemetry is not None and isinstance(final_state, dict):
            await _stamp_telemetry(telemetry, final_state, config)
        return TurnResult(
            final_state=final_state,
            config=config,
            interrupted=False,
            error=final_state.get("error") if isinstance(final_state, dict) else None,
            response=extract_response(final_state)
            if isinstance(final_state, dict)
            else "",
        )
    finally:
        _release_abort_token(container, thread_id, abort_token)
        current_turn_telemetry.reset(token)
        if registry is not None and not interrupted:
            await _close(registry, telemetry, thread_id)


async def invoke_retry_turn(
    container: Container,
    thread_id: str,
    user_text: str,
    *,
    replaces: UUID,
    config_extra: dict | None = None,
) -> TurnResult:
    """Regenerate the latest reply for `user_text` under the one retry policy.

    Rewinds the thread's checkpointed history past the original exchange and runs the
    graph in ``retry_mode``: irreversible writes are refused, reversible writes run
    under normal gates. A run that pauses for confirmation is returned as is; the
    pending turn carries ``retry_mode`` and ``retry_replaces`` so its resolution can
    supersede the retried reply. History is restored only when the run fails or
    produces no reply. The caller must hold the thread's turn lock.
    """
    from ze_agents.errors import RetryFailedError
    from ze_core.conversation.rewind import restore_messages, rewind_last_exchange

    extra = {
        **(config_extra or {}),
        "retry_mode": True,
        "retry_replaces": str(replaces),
    }
    config = container._build_config(thread_id, **extra)
    original = await rewind_last_exchange(container.graph, config)
    try:
        result = await invoke_raw_turn(
            container, thread_id, RawInput(text=user_text), config_extra=extra
        )
    except Exception as exc:
        await restore_messages(container.graph, config, original)
        raise RetryFailedError(str(exc)) from exc
    if result.interrupted and not result.error:
        return result
    if result.error or not result.has_reply:
        await restore_messages(container.graph, config, original)
        raise RetryFailedError(result.error or "empty reply")
    return result
