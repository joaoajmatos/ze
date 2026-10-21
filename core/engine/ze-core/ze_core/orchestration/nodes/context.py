from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from langchain_core.runnables import RunnableConfig

from ze_logging import get_logger
from ze_agents.screen import ScreenContext
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
PRESET_TIMEOUT_SECONDS = 2.0
_PRESET_TOPIC_MAX = 120


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


_COMPANION_AGENT = "companion"


@dataclass(frozen=True)
class _PresetRequest:
    kind: str  # "slipping" | "decisions" | "topic"
    topic: str | None
    key: str  # what AgentContext.preset carries; a show_* tool compares its own key


def _preset_request(screen_ctx: ScreenContext) -> _PresetRequest | None:
    compose = screen_ctx.compose
    if compose is None:
        return None
    if compose in ("slipping", "decisions"):
        return _PresetRequest(compose, None, compose)
    if compose == "topic":
        topic = (screen_ctx.topic or "").strip()
        if topic and len(topic) <= _PRESET_TOPIC_MAX:
            # Same normalization as ze_priority.compose.tools.topic_key.
            return _PresetRequest(
                "topic", topic, "topic:" + " ".join(topic.lower().split())
            )
    log.warning("preset_compose_invalid", compose=compose)
    return None


async def _compose_preset(request: _PresetRequest, composer: Any) -> Any | None:
    try:
        if request.kind == "slipping":
            pending = composer.compose_slipping()
        elif request.kind == "decisions":
            pending = composer.compose_decisions()
        else:
            pending = composer.compose_topic(request.topic)
        return await asyncio.wait_for(pending, timeout=PRESET_TIMEOUT_SECONDS)
    except Exception as exc:
        log.warning("preset_compose_failed", preset=request.key, error=repr(exc))
        return None


def _preset_note(request: _PresetRequest, summary: str) -> str:
    return (
        f'[Composed answer for "{request.key}" — the modules are already on screen. '
        "Write one or two sentences from this only, and offer one next step if it "
        f"helps:\n{summary}]"
    )


def _companion_envelope(
    envelope: RoutingEnvelope | None, config: RunnableConfig, routing_method: str
) -> RoutingEnvelope | None:
    """Reroute a single-agent open-query or preset turn to companion.

    The merged PriorityView and the composed answers are not any specialist's data:
    the goals agent would answer with its own goals only.
    Forced (eval) routes, compound turns and an absent companion stay as routed.
    """
    from ze_agents.registry import get_enabled_agents

    if envelope is None or not envelope.subtasks or envelope.is_compound:
        return None
    if envelope.primary_agent == _COMPANION_AGENT:
        return None
    if config["configurable"].get("forced_agent"):
        return None
    if _COMPANION_AGENT not in get_enabled_agents():
        return None
    router = config["configurable"].get("router")
    model = resolve_agent_model(
        _COMPANION_AGENT, "full", router._app_config if router is not None else {}
    )
    prompt = envelope.subtasks[0].prompt
    return RoutingEnvelope(
        primary_agent=_COMPANION_AGENT,
        confidence=1.0,
        score_gap=0.0,
        routing_method=routing_method,
        is_compound=False,
        subtasks=[
            SubTask(
                agent=_COMPANION_AGENT,
                prompt=prompt,
                model=model,
            )
        ],
        requires_synthesis=False,
        raw_scores={_COMPANION_AGENT: 1.0},
        threshold=envelope.threshold,
        gap_threshold=envelope.gap_threshold,
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
    prompt_embedding = embedder.encode_query(embed_text)
    # The open-query detector is calibrated passage-vs-passage (eval/calibration/open_query.py);
    # query-vs-query loses recall at the same false-positive rate.
    open_items_query = _is_open_query(embedder.encode_passage(embed_text), config)
    screen_ctx = config["configurable"].get("screen_context") or ScreenContext()
    composer = config["configurable"].get("world_composer")
    preset = _preset_request(screen_ctx) if composer is not None else None
    rerouted: RoutingEnvelope | None = None
    if preset is not None:
        rerouted = _companion_envelope(envelope, config, "preset")
        if rerouted is not None:
            envelope = rerouted
            log.info(
                "preset_rerouted", session_id=state["session_id"], preset=preset.key
            )
    elif open_items_query:
        rerouted = _companion_envelope(envelope, config, "open_query")
        if rerouted is not None:
            envelope = rerouted
            log.info("open_query_rerouted", session_id=state["session_id"])
    agent_name = (
        envelope.subtasks[0].agent if envelope and envelope.subtasks else "global"
    )

    _request = RetrievalRequest(
        module=agent_name,
        agent=agent_name,
        query_text=embed_text,
        query_embedding=prompt_embedding,
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

    agent_context.screen_context_note = state.get("screen_note")

    preset_components: list[dict] = []
    if preset is not None:
        composition = await _compose_preset(preset, composer)
        if composition is not None:
            preset_components = list(composition.components)
            agent_context.preset = preset.key
            agent_context.preset_note = _preset_note(preset, composition.summary)

    updates: dict[str, Any] = {}
    if rerouted is not None:
        updates["envelope"] = rerouted
    return {
        **updates,
        "preset_components": preset_components,
        "memory_context": memory_context,
        "agent_context": agent_context,
        "last_active_at": now,
        "resume_recap_applied": resume_recap_applied,
        "loop_offer_ids": loop_offer_ids,
        "open_items_query": open_items_query,
        "procedure_matches": getattr(agent_context, "procedure_matches", None),
    }
