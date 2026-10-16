from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import timezone as _tz
from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from ze_logging import get_logger
from ze_agents.types import AgentContext, RetrievalRequest
from ze_core.orchestration.state import AgentState
from ze_core.routing.tier import resolve_agent_model
from ze_core.routing.types import RoutingEnvelope, SubTask

log = get_logger(__name__)

SESSION_HISTORY_LIMIT = 10
# Mirror ze_priority.turn.RECAP_LIMIT / OPEN_QUERY_LIMIT (ze_core cannot import ze_priority).
_RECAP_LIMIT = 5
_OPEN_QUERY_LIMIT = 10
_DEFAULT_INACTIVITY_MINUTES = 30


@dataclass
class ResumeRecap:
    session_narrative: str | None
    open_item_lines: list[str] = field(default_factory=list)
    in_flight_workflow_lines: list[str] = field(default_factory=list)
    loop_offers: list[Any] = field(default_factory=list)
    gap_minutes: float = 0.0

    def has_content(self) -> bool:
        return bool(
            self.session_narrative
            or self.open_item_lines
            or self.in_flight_workflow_lines
            or self.loop_offers
        )

    def render(self) -> str:
        lines = [
            "[Resuming after a gap — outstanding context, not visible to the user]"
        ]
        if self.session_narrative:
            lines.append(f"Last session: {self.session_narrative}")
        if self.open_item_lines:
            lines.append("Still open:")
            lines.extend(f"- {line}" for line in self.open_item_lines)
        if self.in_flight_workflow_lines:
            lines.append("In-flight workflows:")
            lines.extend(f"- {line}" for line in self.in_flight_workflow_lines)
        if self.loop_offers:
            lines.append(
                "Not yet tracked (Ze noticed these; the user has not confirmed them):"
            )
            lines.extend(f"- {offer.title}" for offer in self.loop_offers)
            lines.append(
                "End your reply with one short question, in the user's language, "
                "asking whether they want you to keep track of these. "
                "Do not say they are being tracked."
            )
        return "\n".join(lines)


async def _assemble_resume_recap(
    session_id: str,
    config: RunnableConfig,
    gap_minutes: float,
) -> ResumeRecap | None:
    configurable = config["configurable"]

    session_narrative: str | None = None
    memory_store = configurable.get("memory_store")
    if memory_store is not None and hasattr(memory_store, "get_session_summary"):
        try:
            summary = await memory_store.get_session_summary(session_id)
            session_narrative = summary.summary if summary is not None else None
        except Exception as exc:
            log.warning("resume_recap_session_summary_failed", error=str(exc))

    open_item_lines: list[str] = []
    surfacer = configurable.get("turn_surfacer")
    if surfacer is not None:
        try:
            mentions = await surfacer.recap_mentions(limit=_RECAP_LIMIT)
            open_item_lines = [m.mention_text for m in mentions]
        except Exception as exc:
            log.warning("resume_recap_turn_surfacing_failed", error=str(exc))

    loop_offers: list[Any] = []
    if surfacer is not None and not configurable.get("retry_mode"):
        try:
            loop_offers = list(await surfacer.resume_loop_offers())
        except Exception as exc:
            log.warning("resume_recap_loop_offers_failed", error=str(exc))

    in_flight_workflow_lines: list[str] = []
    workflow_store = configurable.get("workflow_store")
    if workflow_store is not None:
        try:
            workflows = await workflow_store.list_all()
            for wf in workflows:
                executions = await workflow_store.list_executions(wf.id, limit=1)
                if executions and executions[0].status == "running":
                    in_flight_workflow_lines.append(wf.name)
        except Exception as exc:
            log.warning("resume_recap_workflow_listing_failed", error=str(exc))

    recap = ResumeRecap(
        session_narrative=session_narrative,
        open_item_lines=open_item_lines,
        in_flight_workflow_lines=in_flight_workflow_lines,
        loop_offers=loop_offers,
        gap_minutes=gap_minutes,
    )
    return recap if recap.has_content() else None


def _is_open_query(embedding: Any, config: RunnableConfig) -> bool:
    surfacer = config["configurable"].get("turn_surfacer")
    if surfacer is None:
        return False
    try:
        return bool(surfacer.is_global_open_query(embedding))
    except Exception as exc:
        log.warning("open_query_detection_failed", error=str(exc))
        return False


async def _open_priorities_note(
    open_items_query: bool, config: RunnableConfig
) -> str | None:
    surfacer = config["configurable"].get("turn_surfacer")
    if surfacer is None or not open_items_query:
        return None
    try:
        mentions = await surfacer.open_query_mentions(limit=_OPEN_QUERY_LIMIT)
    except Exception as exc:
        log.warning("open_priorities_note_failed", error=str(exc))
        return None
    if not mentions:
        return None
    lines = ["[Open priorities — ranked, including items you pinned:]"]
    for mention in mentions:
        lines.append(f"- {mention.mention_text}")
    return "\n".join(lines)


_OPEN_QUERY_AGENT = "companion"
_OPEN_QUERY_INTENT = "reason"


def _open_query_envelope(
    envelope: RoutingEnvelope | None, config: RunnableConfig
) -> RoutingEnvelope | None:
    """Reroute a single-agent "what's open?" turn to companion.

    The merged PriorityView is not any specialist's data: the goals agent would
    answer with its own goals and gate on whichever intent it declares first.
    Forced (eval) routes, compound turns and an absent companion stay as routed.
    """
    from ze_agents.registry import get_enabled_agents

    if envelope is None or not envelope.subtasks or envelope.is_compound:
        return None
    if envelope.primary_agent == _OPEN_QUERY_AGENT:
        return None
    if config["configurable"].get("forced_agent"):
        return None
    if _OPEN_QUERY_AGENT not in get_enabled_agents():
        return None
    router = config["configurable"].get("router")
    model = resolve_agent_model(
        _OPEN_QUERY_AGENT, "full", router._app_config if router is not None else {}
    )
    prompt = envelope.subtasks[0].prompt
    return RoutingEnvelope(
        primary_agent=_OPEN_QUERY_AGENT,
        confidence=1.0,
        score_gap=0.0,
        routing_method="open_query",
        is_compound=False,
        subtasks=[
            SubTask(
                agent=_OPEN_QUERY_AGENT,
                intent=_OPEN_QUERY_INTENT,
                prompt=prompt,
                model=model,
            )
        ],
        requires_synthesis=False,
        raw_scores={_OPEN_QUERY_AGENT: 1.0},
    )


async def fetch_context(state: AgentState, config: RunnableConfig) -> dict:
    store: Any = config["configurable"]["memory_store"]
    embedder: Any = config["configurable"]["embedder"]
    cfg: Any = config["configurable"].get("settings")

    inactivity_minutes = _DEFAULT_INACTIVITY_MINUTES
    if cfg is not None:
        inactivity_minutes = getattr(cfg, "session_inactivity_minutes", None) or (
            cfg.get("session_inactivity_minutes", _DEFAULT_INACTIVITY_MINUTES)
            if isinstance(cfg, dict)
            else _DEFAULT_INACTIVITY_MINUTES
        )

    persona_store: Any = config["configurable"].get("persona_store")
    person_store: Any = config["configurable"].get("person_store")

    envelope = state.get("envelope")
    embed_text = state.get("image_caption") or state["prompt"]
    prompt_embedding = embedder.encode(embed_text)
    open_items_query = _is_open_query(prompt_embedding, config)
    rerouted: RoutingEnvelope | None = None
    if open_items_query:
        rerouted = _open_query_envelope(envelope, config)
        if rerouted is not None:
            envelope = rerouted
            log.info("open_query_rerouted", session_id=state["session_id"])
    agent_name = (
        envelope.subtasks[0].agent if envelope and envelope.subtasks else "global"
    )
    intent = envelope.subtasks[0].intent if envelope and envelope.subtasks else "read"

    _request = RetrievalRequest(
        module=agent_name,
        agent=agent_name,
        query_text=embed_text,
        query_embedding=prompt_embedding,
        intent=intent,
        task_id=None,
        goal_id=None,
        max_tokens=2000,
        current_session_id=state.get("session_id"),
    )
    memory_context = await store.retrieve(_request)

    active_persona: dict = {}
    if persona_store is not None:
        active_persona = await persona_store.get_active() or {}

    now = time.time()
    last_active = state.get("last_active_at")
    recap: ResumeRecap | None = None
    resume_recap_applied = False
    loop_offer_ids: list[str] = []
    if last_active and (now - last_active) > (inactivity_minutes * 60):
        history: list[dict] = []
        log.info("session_expired", session_id=state["session_id"])
        gap_minutes = (now - last_active) / 60
        recap = await _assemble_resume_recap(state["session_id"], config, gap_minutes)
        resume_recap_applied = recap is not None
        if recap is not None:
            loop_offer_ids = [str(offer.loop_id) for offer in recap.loop_offers]
    else:
        history = list(state.get("messages") or [])

    if state.get("input_modality") == "image":
        user_text = state.get("image_caption") or state.get("prompt") or "(image)"
    else:
        user_text = state["prompt"]
    messages = history + [{"role": "user", "content": user_text}]

    prompt_for_ctx = state.get("image_caption") or state["prompt"]

    contact_context: Any = None
    if person_store is not None:
        contact_context = await person_store.get_context(prompt_for_ctx)

    tz = "UTC"
    if cfg is not None:
        tz = getattr(cfg, "timezone", None) or (
            cfg.get("timezone", "UTC") if isinstance(cfg, dict) else "UTC"
        )

    agent_context = AgentContext(
        session_id=state["session_id"],
        prompt=prompt_for_ctx,
        intent=intent,
        memory=memory_context,
        contacts=contact_context,
        messages=messages,
        persona=active_persona,
        timezone=tz,
    )
    agent_context.retry_mode = bool(config["configurable"].get("retry_mode"))
    if recap is not None:
        agent_context.resume_recap = recap.render()
    note = await _open_priorities_note(open_items_query, config)
    if note is not None:
        agent_context.open_priorities_note = note

    from ze_core.orchestration.procedure_activation import attach_procedure_matches

    await attach_procedure_matches(agent_context, config, agent_name)

    hint = state.get("conductor_hint")
    ledger = state.get("conductor_ledger")
    agent_context.conductor_hint = hint
    agent_context.conductor_ledger = ledger if ledger is not None else []
    agent_context.conductor_delegate_counts = dict(
        state.get("conductor_delegate_counts") or {}
    )
    agent_context.conductor_delegate_total = int(
        state.get("conductor_delegate_total") or 0
    )

    user_message_id = config["configurable"].get("user_message_id")
    if user_message_id is not None:
        agent_context.extensions["user_message_id"] = user_message_id

    screen_ctx = config["configurable"].get("screen_context") or {}
    workflow_id = screen_ctx.get("workflow_id")
    execution_id = screen_ctx.get("execution_id")
    if workflow_id:
        wf_store = config["configurable"].get("workflow_store")
        if wf_store is not None:
            try:
                wf = await wf_store.get(UUID(str(workflow_id)))
                if wf:
                    executions = await wf_store.list_executions(wf.id, limit=20)
                    ex = (
                        next(
                            (e for e in executions if str(e.id) == str(execution_id)),
                            None,
                        )
                        if execution_id
                        else None
                    )
                    agent_context.screen_context_note = _build_screen_context_note(
                        wf, ex
                    )
            except Exception:
                pass  # best-effort; never block the turn

    placed = screen_ctx.get("workspace_placed") or []
    if placed:
        lines = [
            "[Workspace: the user placed these files in the workspace this turn "
            "(they are not ingested unless you call ingest_workspace_file)]"
        ]
        for item in placed:
            if isinstance(item, dict):
                path = item.get("path") or ""
                size = item.get("size")
                extra = f" ({size} bytes)" if size is not None else ""
                lines.append(f"- {path}{extra}")
            else:
                lines.append(f"- {item}")
        note = "\n".join(lines)
        existing = agent_context.screen_context_note
        agent_context.screen_context_note = (
            f"{existing}\n\n{note}" if existing else note
        )

    updates: dict[str, Any] = {}
    if rerouted is not None:
        updates["envelope"] = rerouted
    return {
        **updates,
        "memory_context": memory_context,
        "agent_context": agent_context,
        "last_active_at": now,
        "resume_recap_applied": resume_recap_applied,
        "loop_offer_ids": loop_offer_ids,
        "open_items_query": open_items_query,
        "procedure_matches": getattr(agent_context, "procedure_matches", None),
    }


def _build_screen_context_note(wf: Any, ex: Any) -> str:
    lines = [f"[Screen context: user is viewing workflow '{wf.name}']"]
    if ex:
        duration_s: str | None = None
        if ex.started_at and ex.completed_at:
            started = (
                ex.started_at.replace(tzinfo=_tz.utc)
                if ex.started_at.tzinfo is None
                else ex.started_at
            )
            completed = (
                ex.completed_at.replace(tzinfo=_tz.utc)
                if ex.completed_at.tzinfo is None
                else ex.completed_at
            )
            secs = int((completed - started).total_seconds())
            duration_s = f"{secs}s"
        step_count = len(ex.step_results) if ex.step_results else 0
        parts = [f"status={ex.status}", f"steps={step_count}"]
        if duration_s:
            parts.append(f"duration={duration_s}")
        lines.append(f"Run: {', '.join(parts)}")
        if ex.error:
            lines.append(f"Error: {ex.error}")
    return "\n".join(lines)
