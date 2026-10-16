from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from ze_plugin.plugin import ZePlugin

from ze_agents.types import GateDecision
from ze_agents.types import AgentContext, AgentResult
from ze_core.routing.types import RoutingEnvelope


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────
    prompt: str
    session_id: str
    session_overrides: dict[str, str]  # "agent.intent" → mode string

    # ── Multimodal ─────────────────────────────────────────────────────────
    input_modality: str  # "text" | "voice" | "image" — default "text"
    audio_data: (
        bytes | None
    )  # raw audio bytes; cleared after preprocess transcribes them
    audio_mime: str | None  # e.g. "audio/ogg; codecs=opus"
    image_data: bytes | None  # raw image bytes; None for text/voice turns
    image_mime: str | None  # "image/jpeg" | "image/png" | None
    image_caption: str | None  # caption generated at preprocess; None until set

    # ── Routing ────────────────────────────────────────────────────────────
    envelope: RoutingEnvelope | None

    # ── Context ────────────────────────────────────────────────────────────
    memory_context: Any | None
    agent_context: AgentContext | None

    # ── Capability ─────────────────────────────────────────────────────────
    gate_decision: GateDecision | None
    subtask_gate_decisions: (
        list  # list[{agent, intent, decision}] aligned with envelope.subtasks
    )

    # ── Execution ──────────────────────────────────────────────────────────
    agent_result: AgentResult | None
    subtask_results: list[AgentResult]
    completed_subtask_indexes: list[int]
    pending_subtask_awaits: list  # list[{index, agent, intent, prompt, request_id}]
    approved_subtask_indexes: list[int]
    denied_subtask_indexes: list[int]
    pending_confirmation: bool
    approved_agents: list[str]  # agents whose confirmation gate the user approved

    # ── Write confirmation (Phase 181) ─────────────────────────────────────
    blocked: bool  # set by preflight when every routed agent is disabled
    budget_status: dict | None  # set by preflight when the turn is over budget
    budget_approved: bool
    parked_subtasks: list  # list[ParkedSubtask]; loops waiting on the user
    write_confirmation: Any | None  # WriteConfirmation; the open one
    write_decisions: list  # list[WriteDecision]; answers to the open one
    write_rounds: int  # confirmations answered this turn
    write_outcomes: list  # list[dict]; per item, every round; copied to the trace

    # ── Conversation history ───────────────────────────────────────────────
    messages: list[dict]
    last_active_at: float | None
    compaction_span: tuple[int, int] | None  # set by write_memory when it compacts
    resume_recap_applied: bool  # set by fetch_context's resume-recap branch
    open_items_query: bool  # set by fetch_context every turn; read by surface_loops
    loop_offer_ids: list[str]  # set by fetch_context every turn; read by record_trace

    # ── Output ─────────────────────────────────────────────────────────────
    final_response: str | None
    error: str | None
    components: list[dict]

    # ── Conductor (Phase 153 — sequential rewrite; not a DAG) ──────────────
    conductor_hint: list | None  # list[{agent, intent, prompt}]
    conductor_ledger: list  # list[{agent, status, request_id?}]
    conductor_delegate_counts: dict  # agent name → attempted delegates this turn
    conductor_delegate_total: int

    # ── Correlation (Phase 58 — populated by correlate node) ──────────────────
    correlations: list  # list[Hypothesis]; qualifying inline hypotheses

    # ── Routing context (populated by pre-route plugin nodes) ────────────────
    routing_hints: str | None  # injected by inject_goal_routing_context

    # ── Trace (Phase 89 — populated by record_trace node) ────────────────────
    message_trace: Any | None  # MessageTrace; saved to DB after message is persisted
    judgments: list  # list[JudgmentTrace]; reset each turn, copied by record_trace

    # ── Skills (Phase 114 — populated by match_skills node) ──────────────────
    skill_matches: (
        Any | None
    )  # list[SkillMatch] (ze_skills, kept untyped — no ze_core dep)

    # ── Procedures (Phase 139 — advisory matches live on AgentContext) ──────
    procedure_matches: Any | None


def build_state_type(plugins: list[ZePlugin]) -> type:
    """Return a TypedDict class that merges AgentState with all plugin state extensions.

    Each plugin's state_extensions() returns a plain TypedDict of its own fields; plugins
    never import AgentState. The merged class inherits AgentState and every extension, so
    all fields are accessible via the standard state["field"] syntax in graph nodes.

    Returns AgentState unchanged when no plugins contribute state extensions.
    """
    extensions = [
        p.state_extensions() for p in plugins if p.state_extensions() is not None
    ]
    if not extensions:
        return AgentState
    # TypedDict supports multiple inheritance; Python resolves the metaclass from bases.
    # An extension that still subclasses AgentState forms a diamond with it, which is fine.
    return type(
        "ExtendedAgentState", (AgentState, *extensions), {"__annotations__": {}}
    )
