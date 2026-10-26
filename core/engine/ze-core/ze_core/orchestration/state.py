from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Awaitable, Callable, TypedDict

from langchain_core.runnables import RunnableConfig

if TYPE_CHECKING:
    from ze_plugin.plugin import ZePlugin

from ze_agents.lifetime import Input, Thread, Turn, field_lifetimes, turn_reset
from ze_agents.types import AgentContext, AgentResult, ProcedureInvocation
from ze_core.routing.types import RoutingEnvelope

# Every field declares its lifetime (`ze_agents.lifetime`): `Turn` fields are reset at the
# start of each turn (and each workflow step) to the declared value, `Input` fields come from
# whoever starts the turn, `Thread` fields survive across turns. The new-turn graph input is
# generated from these markers, so there is no second list to keep in step.


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────
    prompt: Annotated[str, Input()]
    session_id: Annotated[str, Input()]

    # ── Multimodal ─────────────────────────────────────────────────────────
    input_modality: Annotated[str, Input()]  # "text" | "voice" | "image"
    voice_input: Annotated[
        dict | None, Input()
    ]  # {"duration_s", "edited"} for a transcribed voice turn
    image_data: Annotated[bytes | None, Input()]  # raw image bytes; None for text/voice
    image_mime: Annotated[str | None, Input()]  # "image/jpeg" | "image/png" | None
    image_caption: Annotated[str | None, Turn()]  # caption generated at preprocess

    # ── Routing ────────────────────────────────────────────────────────────
    envelope: Annotated[RoutingEnvelope | None, Turn()]

    # ── Context ────────────────────────────────────────────────────────────
    memory_context: Annotated[Any | None, Turn()]
    agent_context: Annotated[AgentContext | None, Turn()]

    # ── Execution ──────────────────────────────────────────────────────────
    agent_result: Annotated[AgentResult | None, Turn()]
    subtask_results: Annotated[list[AgentResult], Turn(factory=list)]
    completed_subtask_indexes: Annotated[list[int], Turn(factory=list)]

    # ── Write confirmation (Phase 181) ─────────────────────────────────────
    blocked: Annotated[bool, Turn(reset=False)]  # set by preflight: all agents disabled
    budget_status: Annotated[dict | None, Turn()]  # set by preflight when over budget
    budget_approved: Annotated[bool, Turn(reset=False)]
    parked_subtasks: Annotated[
        list, Turn(factory=list)
    ]  # list[ParkedSubtask]; loops waiting on the user
    write_confirmation: Annotated[Any | None, Turn()]  # WriteConfirmation; the open one
    write_decisions: Annotated[
        list, Turn(factory=list)
    ]  # list[WriteDecision]; answers to the open one
    write_rounds: Annotated[int, Turn(reset=0)]  # confirmations answered this turn
    write_outcomes: Annotated[
        list, Turn(factory=list)
    ]  # list[dict]; per item, every round; copied to the trace
    pre_approved_writes: Annotated[
        list, Turn(factory=list)
    ]  # list[str]; tools a workflow step or milestone may run unasked

    # ── Conversation history ───────────────────────────────────────────────
    messages: Annotated[
        list[dict], Thread("history must survive across turns; write_memory appends")
    ]
    last_active_at: Annotated[
        float | None, Thread("the gap since the last turn drives the resume recap")
    ]
    resume_recap_applied: Annotated[bool, Turn(reset=False)]  # set by fetch_context
    open_items_query: Annotated[bool, Turn(reset=False)]  # set by fetch_context
    loop_offer_ids: Annotated[list[str], Turn(factory=list)]  # read by record_trace

    # ── Output ─────────────────────────────────────────────────────────────
    final_response: Annotated[str | None, Turn()]
    error: Annotated[str | None, Turn()]
    components: Annotated[list[dict], Turn(factory=list)]
    preset_components: Annotated[
        list[dict], Turn(factory=list)
    ]  # composed answer a preset chip asked for

    # ── Conductor (Phase 153 — sequential rewrite; not a DAG) ──────────────
    conductor_hint: Annotated[list | None, Turn()]  # list[{agent, prompt, changes}]
    # One ledger per subtask index; a missing slot reads as []. Each is a
    # list[{agent, status, request_id?}].
    conductor_ledgers: Annotated[list, Turn(factory=list)]
    conductor_delegate_counts: Annotated[
        dict, Turn(factory=dict)
    ]  # agent name → attempted delegates this turn
    conductor_delegate_total: Annotated[int, Turn(reset=0)]

    # ── Procedures (Phase 139/200) ─────────────────────────────────────────
    procedure_invocations: Annotated[
        list[ProcedureInvocation], Turn(factory=list)
    ]  # by subtask; each carries `subtask`

    # ── Correlation (Phase 58 — populated by correlate node) ──────────────────
    correlations: Annotated[list, Turn(factory=list)]  # list[Hypothesis]

    # ── Screen context (Phase 195 — populated by resolve_screen) ─────
    screen_note: Annotated[str | None, Turn()]  # the note fetch_context copies over
    screen_trace: Annotated[
        dict | None, Turn()
    ]  # rows + counts for MessageTrace.screen (plain dict: checkpointed)
    screen_subject_line: Annotated[
        str | None, Turn()
    ]  # routing hint, used only when screen_hint is on

    # ── Routing context (populated by pre-route plugin nodes) ────────────────
    routing_hints: Annotated[str | None, Turn()]  # injected by inject_goal_routing_context

    # ── Trace (Phase 89 — populated by record_trace node) ────────────────────
    message_trace: Annotated[Any | None, Turn()]  # MessageTrace; saved after persist
    judgments: Annotated[list, Turn(factory=list)]  # list[JudgmentTrace]
    tier: Annotated[Any | None, Turn()]  # TierTrace; set by choose_tier

    # ── Skills (Phase 114 — populated by match_skills node) ──────────────────
    skill_matches: Annotated[
        Any | None, Turn()
    ]  # list[SkillMatch] (ze_skills, kept untyped — no ze_core dep)


def build_state_type(plugins: list[ZePlugin]) -> type:
    """Return a TypedDict class that merges AgentState with all plugin state extensions.

    Each plugin's state_extensions() returns a plain TypedDict of its own fields; plugins
    never import AgentState. The merged class inherits AgentState and every extension, so
    all fields are accessible via the standard state["field"] syntax in graph nodes.

    Every field of AgentState and of each extension must declare a lifetime; an undeclared
    field raises `UndeclaredLifetimeError`, so graph build (startup) fails.

    Returns AgentState unchanged when no plugins contribute state extensions.
    """
    field_lifetimes(AgentState)
    extensions = [
        p.state_extensions() for p in plugins if p.state_extensions() is not None
    ]
    for extension in extensions:
        field_lifetimes(extension)
    if not extensions:
        return AgentState
    # TypedDict supports multiple inheritance; Python resolves the metaclass from bases.
    # An extension that still subclasses AgentState forms a diamond with it, which is fine.
    return type(
        "ExtendedAgentState", (AgentState, *extensions), {"__annotations__": {}}
    )


def with_turn_reset(
    node: Callable[..., Awaitable[dict] | dict], state_type: type
) -> Callable[[Any, RunnableConfig], Awaitable[dict]]:
    """Wrap a graph node so its updates start from the turn reset (a workflow step).

    The node's own keys win over the reset values.
    """

    async def wrapped(state: Any, config: RunnableConfig) -> dict:
        result = node(state, config)
        if hasattr(result, "__await__"):
            result = await result
        return {**turn_reset(state_type), **(result or {})}

    wrapped.__name__ = getattr(node, "__name__", "node")
    return wrapped
