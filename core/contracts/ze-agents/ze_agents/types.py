from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable
from uuid import UUID, uuid4

from ze_agents.claims import ClaimKind, Provenance
from ze_agents.park import ParkedLoop, ParkedWrite, WriteDecision


# ── Orchestration types ───────────────────────────────────────────────────────


@dataclass
class AbortToken:
    """Async abort signal for agentic loops. Set from outside; checked per iteration."""

    _event: asyncio.Event = field(default_factory=asyncio.Event)
    reason: str | None = None

    def abort(self, reason: str | None = None) -> None:
        """Signal the running loop to stop after the current tool call completes."""
        self.reason = reason
        self._event.set()

    @property
    def is_set(self) -> bool:
        return self._event.is_set()


@runtime_checkable
class ClaimBearingProposal(Protocol):
    """Structural shape any producer's proposal type must satisfy to sit on
    `AgentResult.contact_proposals` — referenced without this
    package depending on any concrete producer type (Principle III)."""

    claim_kind: ClaimKind
    provenance: Provenance
    confidence: float


class IdentityBuilder(Protocol):
    """Callable that renders the persona/memory preamble injected into agent prompts."""

    def __call__(
        self,
        persona: dict,
        memory_context: str,
        *,
        profile: Any,
        contacts_context: str,
    ) -> str: ...


@dataclass
class Source:
    """A web source a reply drew on, as reported by the search provider."""

    url: str
    title: str = ""


def add_sources(target: list[Source], found: list[Source]) -> None:
    """Append sources to target, skipping URLs it already holds."""
    seen = {s.url for s in target}
    for source in found:
        if source.url and source.url not in seen:
            seen.add(source.url)
            target.append(source)


@dataclass
class ToolCall:
    tool_name: str
    args: dict[str, Any]
    result: Any
    duration_ms: int
    success: bool
    error: str | None = None
    # "none" | "approved" | "pre_approved" | "parked" | "denied" | "refused" | "refused_over_cap" | "expired" | "duplicate"
    gate: str = "none"
    parked: ParkedWrite | None = None
    child_loop: ParkedLoop | None = None
    # {request_id, outcome} for approved/edited calls; {outcome: "pre_approved"} for unattended
    approval: dict[str, Any] | None = None
    agent: str | None = None
    undo: dict[str, Any] | None = None
    # call_id joins a live tool row to its committed row; a parked call and its approved
    # run share ParkedWrite.trace_call_id. started_at is time.monotonic() seconds.
    call_id: str = field(default_factory=lambda: uuid4().hex)
    started_at: float | None = None
    # A script step holds the calls its script made; each inner call and each proposed
    # write names the step through parent_call_id. `script` is the step's trace summary
    # (source, source_cut, outcome, limit, source_hash, procedure_id).
    parent_call_id: str | None = None
    inner_calls: list[ToolCall] = field(default_factory=list)
    script: dict[str, Any] | None = None


@dataclass
class WriteGateState:
    """The part of a context the write gates read (phases 165 and 181).

    `loop_active` is set only by the agent's own loop; every derivation starts it False.
    Runtime/turn-local: never checkpoint a context.
    """

    # The saved loop to re-enter after the user answered.
    resume: ParkedLoop | None = None
    decisions: dict[str, WriteDecision] = field(default_factory=dict)
    pre_approved: frozenset[str] = frozenset()
    round: int = 0
    approval_request_id: str | None = None
    loop_active: bool = False
    # Phase 165: a retry run regenerates text only; WRITE tools are refused.
    retry_mode: bool = False


@dataclass
class DelegateTally:
    """Delegates made in one turn. One object is shared by every subtask of a pass."""

    counts: dict[str, int] = field(default_factory=dict)
    total: int = 0


@dataclass
class ConductorState:
    """The conductor's state for one run (phase 153). Primitives only, except `tally`."""

    hint: list[dict[str, str]] | None = None
    ledger: list[dict[str, str]] = field(default_factory=list)
    tally: DelegateTally = field(default_factory=DelegateTally)
    # Run-local; never written to graph state. Kept off `extensions` so a delegate that
    # inherits `extensions` does not inherit the companion's deadline.
    deadline: float | None = None
    stalls: dict[str, str] = field(default_factory=dict)


@dataclass
class ProcedureInvocation:
    """A procedure `invoke_procedure` started in this run (phase 139)."""

    invocation_id: str
    procedure_id: str
    version_id: str
    # The narrowing: only ever intersects an agent's tools.
    tool_names: list[str] = field(default_factory=list)
    # Which subtask invoked it (0 outside a compound turn).
    subtask: int = 0


@dataclass
class AgentContext:
    session_id: str
    prompt: str
    memory: Any = None
    contacts: Any = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    persona: dict = field(default_factory=dict)
    model: str | None = None
    reporter: Any = field(default=None, repr=False)  # ProgressReporter | None
    # identity_builder is runtime-only (a callable); always None in stored state.
    # Never checkpoint a context where this is set — the serde test enforces that.
    identity_builder: IdentityBuilder | None = field(default=None, repr=False)
    # abort_token is runtime-only; never checkpoint a context where this is set.
    abort_token: AbortToken | None = field(default=None, repr=False)
    # memory_store is runtime-only; set by GoalExecutor for direct agent invocations
    # that bypass the fetch_context graph node. Never checkpoint.
    memory_store: Any = field(default=None, repr=False)
    # embed_fn is runtime-only; injected by the container so BaseAgent can compute
    # embeddings without importing ze-core. Never checkpoint.
    embed_fn: Callable[[str], Any] | None = field(default=None, repr=False)
    # token_sink is runtime-only; when set, agentic_loop streams tokens to it.
    # Signature: async (chunk: str) -> None. Never checkpoint.
    token_sink: Any | None = field(default=None, repr=False)
    # tool_sink is runtime-only; call_tool hands every finished ToolCall to it.
    # Signature: (call: ToolCall) -> None, must not block. Never checkpoint.
    tool_sink: Any | None = field(default=None, repr=False)
    # sources collects web citations reported while this context's agent runs
    # (appended by agentic_loop, merged upward by delegate_to_agent). Empty in
    # any stored context.
    sources: list[Source] = field(default_factory=list)
    # screen_context_note is runtime-only; built by the resolve_screen node from the
    # client's screen context and copied here by fetch_context. Never checkpoint.
    screen_context_note: str | None = field(default=None, repr=False)
    # preset_note is runtime-only; the composed-answer summary for a preset turn (phase 184),
    # rendered after the screen note. Never checkpoint.
    preset_note: str | None = field(default=None, repr=False)
    # resume_recap is runtime-only; injected by fetch_context's resume-recap branch
    # on a long-gap turn. Rendered into the system prompt, never appended to
    # messages — must never surface as a visible chat message. Never checkpoint.
    resume_recap: str | None = field(default=None, repr=False)
    # open_priorities_note is runtime-only; injected by fetch_context when the
    # user explicitly asks what's open. Rendered into the system prompt, never
    # appended to messages. Never checkpoint.
    open_priorities_note: str | None = field(default=None, repr=False)
    # preset is runtime-only; the key of the composed answer fetch_context already put
    # at the head of this turn ("slipping", "decisions", "topic:<normalized>"). The show_*
    # tools return only their summary when it matches their own key. Never checkpoint.
    preset: str | None = field(default=None, repr=False)
    # active_skills / skill_tool_names are populated by the `match_skills` orchestration
    # node from the turn's `SkillMatch` list (core/automation/ze-skills). `active_skills` holds the
    # matched `Skill` objects (name/description/instructions injected into the system
    # prompt); `skill_tool_names`, when not None, is the intersection of every matched
    # skill's `allowed_tools` and must only ever narrow — never union — an agent's own
    # `tools` (FR-008). Never checkpoint: skills are re-matched fresh on resume.
    active_skills: list[Any] = field(default_factory=list, repr=False)
    skill_tool_names: list[str] | None = field(default=None, repr=False)
    # Procedure discovery (Phase 139). Matches are advisory until invoke_procedure sets
    # `procedure_invocation`, whose tool_names only ever narrow. Never checkpoint.
    procedure_guidance: str | None = field(default=None, repr=False)
    # script_runner is runtime-only; set from the turn config so agentic_loop can offer
    # run_tool_script. Never checkpoint.
    script_runner: Any | None = field(default=None, repr=False)
    procedure_matches: list[Any] | None = field(default=None, repr=False)
    procedure_invocation: ProcedureInvocation | None = field(default=None, repr=False)
    # Turn-local conductor state (Phase 153): hint, this run's ledger, the shared tally.
    conductor: ConductorState = field(default_factory=ConductorState)
    # Everything the write gates read (phases 165, 181). Derived as one unit.
    write_gate: WriteGateState = field(default_factory=WriteGateState)
    # extensions must hold only msgpack-serializable primitives so stored contexts
    # can be checkpointed. Use identity_builder for callable injection instead.
    extensions: dict[str, str | int | float | bool | None] = field(default_factory=dict)
    timezone: str = "UTC"


@dataclass
class RetrievalRequest:
    module: str
    agent: str
    query_text: str
    query_embedding: Any
    task_id: UUID | None = None
    goal_id: UUID | None = None
    max_tokens: int = 2000
    current_session_id: str | None = None


@dataclass
class AgentResult:
    agent: str
    response: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_used: int = 0
    contact_proposals: list[ClaimBearingProposal] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)
    sources: list[Source] = field(default_factory=list)
