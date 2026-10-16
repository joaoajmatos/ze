from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable
from uuid import UUID

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
    # "none" | "approved" | "pre_approved" | "parked" | "denied" | "refused_over_cap" | "expired"
    gate: str = "none"
    parked: ParkedWrite | None = None
    child_loop: ParkedLoop | None = None
    # {request_id, outcome} for approved/edited calls; {outcome: "pre_approved"} for unattended
    approval: dict[str, Any] | None = None


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
    # sources collects web citations reported while this context's agent runs
    # (appended by agentic_loop, merged upward by delegate_to_agent). Empty in
    # any stored context.
    sources: list[Source] = field(default_factory=list)
    # screen_context_note is runtime-only; injected by fetch_context when the client
    # sends a WsScreenContext (e.g. viewing a specific workflow execution). Never checkpoint.
    screen_context_note: str | None = field(default=None, repr=False)
    # resume_recap is runtime-only; injected by fetch_context's resume-recap branch
    # on a long-gap turn. Rendered into the system prompt, never appended to
    # messages — must never surface as a visible chat message. Never checkpoint.
    resume_recap: str | None = field(default=None, repr=False)
    # open_priorities_note is runtime-only; injected by fetch_context when the
    # user explicitly asks what's open. Rendered into the system prompt, never
    # appended to messages. Never checkpoint.
    open_priorities_note: str | None = field(default=None, repr=False)
    # active_skills / skill_tool_names are populated by the `match_skills` orchestration
    # node from the turn's `SkillMatch` list (core/automation/ze-skills). `active_skills` holds the
    # matched `Skill` objects (name/description/instructions injected into the system
    # prompt); `skill_tool_names`, when not None, is the intersection of every matched
    # skill's `allowed_tools` and must only ever narrow — never union — an agent's own
    # `tools` (FR-008). Never checkpoint: skills are re-matched fresh on resume.
    active_skills: list[Any] = field(default_factory=list, repr=False)
    skill_tool_names: list[str] | None = field(default=None, repr=False)
    # Procedure discovery/activation (Phase 139). Matches are advisory until
    # invoke_procedure; procedure_tool_names only ever narrows. Never checkpoint.
    procedure_guidance: str | None = field(default=None, repr=False)
    procedure_matches: list[Any] | None = field(default=None, repr=False)
    procedure_tool_names: list[str] | None = field(default=None, repr=False)
    procedure_invocation_id: str | None = field(default=None, repr=False)
    procedure_invoked_id: str | None = field(default=None, repr=False)
    procedure_invoked_version_id: str | None = field(default=None, repr=False)
    # Turn-local conductor hint/ledger (Phase 153). Lists of primitives only.
    conductor_hint: list[dict[str, str]] | None = None
    conductor_ledger: list[dict[str, str]] = field(default_factory=list)
    conductor_delegate_counts: dict[str, int] = field(default_factory=dict)
    conductor_delegate_total: int = 0
    # Phase 165: a retry run regenerates text only; WRITE tools are refused.
    retry_mode: bool = False
    # Phase 181 write confirmation. `resume` is the saved loop to re-enter after the
    # user answered; the rest are runtime/turn-local. Never checkpoint a context.
    resume: ParkedLoop | None = None
    write_decisions: dict[str, WriteDecision] = field(default_factory=dict)
    pre_approved_writes: frozenset[str] = frozenset()
    write_round: int = 0
    approval_request_id: str | None = None
    loop_active: bool = False
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
