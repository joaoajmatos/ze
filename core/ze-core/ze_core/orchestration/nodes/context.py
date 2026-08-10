from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import timezone as _tz
from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from ze_logging import get_logger
from ze_agents.types import AgentContext, RetrievalRequest
from ze_core.orchestration.nodes.loop_surfacing import _extract_seeds
from ze_core.orchestration.state import AgentState

log = get_logger(__name__)

SESSION_HISTORY_LIMIT = 10
_DEFAULT_INACTIVITY_MINUTES = 30


@dataclass
class ResumeRecap:
    session_narrative: str | None
    open_loop_lines: list[str] = field(default_factory=list)
    in_flight_goal_lines: list[str] = field(default_factory=list)
    in_flight_workflow_lines: list[str] = field(default_factory=list)
    gap_minutes: float = 0.0

    def has_content(self) -> bool:
        return bool(
            self.session_narrative
            or self.open_loop_lines
            or self.in_flight_goal_lines
            or self.in_flight_workflow_lines
        )

    def render(self) -> str:
        lines = ["[Resuming after a gap — outstanding context, not visible to the user]"]
        if self.session_narrative:
            lines.append(f"Last session: {self.session_narrative}")
        if self.open_loop_lines:
            lines.append("Still open:")
            lines.extend(f"- {line}" for line in self.open_loop_lines)
        if self.in_flight_goal_lines:
            lines.append("In-flight goals:")
            lines.extend(f"- {line}" for line in self.in_flight_goal_lines)
        if self.in_flight_workflow_lines:
            lines.append("In-flight workflows:")
            lines.extend(f"- {line}" for line in self.in_flight_workflow_lines)
        return "\n".join(lines)


async def _assemble_resume_recap(
    session_id: str,
    memory_context: Any,
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

    open_loop_lines: list[str] = []
    surfacer = configurable.get("loop_surfacer")
    if surfacer is not None:
        try:
            entity_ids = _extract_seeds(memory_context)
            if entity_ids:
                mentions = await surfacer.inline_candidates(entity_ids)
                open_loop_lines = [m.mention_text for m in mentions]
        except Exception as exc:
            log.warning("resume_recap_loop_surfacing_failed", error=str(exc))

    in_flight_goal_lines: list[str] = []
    goal_store = configurable.get("goal_store")
    if goal_store is not None:
        try:
            active_goals = await goal_store.list_active()
            in_flight_goal_lines = [f"{g.title}: {g.objective}" for g in active_goals]
        except Exception as exc:
            log.warning("resume_recap_goal_listing_failed", error=str(exc))

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
        open_loop_lines=open_loop_lines,
        in_flight_goal_lines=in_flight_goal_lines,
        in_flight_workflow_lines=in_flight_workflow_lines,
        gap_minutes=gap_minutes,
    )
    return recap if recap.has_content() else None


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
    agent_name = (
        envelope.subtasks[0].agent if envelope and envelope.subtasks else "global"
    )
    intent = envelope.subtasks[0].intent if envelope and envelope.subtasks else "read"

    embed_text = state.get("image_caption") or state["prompt"]
    prompt_embedding = embedder.encode(embed_text)

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
    if last_active and (now - last_active) > (inactivity_minutes * 60):
        history: list[dict] = []
        log.info("session_expired", session_id=state["session_id"])
        gap_minutes = (now - last_active) / 60
        recap = await _assemble_resume_recap(
            state["session_id"], memory_context, config, gap_minutes
        )
        resume_recap_applied = recap is not None
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
    if recap is not None:
        agent_context.resume_recap = recap.render()

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

    return {
        "memory_context": memory_context,
        "agent_context": agent_context,
        "last_active_at": now,
        "resume_recap_applied": resume_recap_applied,
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
