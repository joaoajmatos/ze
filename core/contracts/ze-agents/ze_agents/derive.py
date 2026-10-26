"""The one place that derives a child `AgentContext`.

Every agent run in a turn is built from the turn's facts: a routed specialist or compound
subtask (`for_subtask`), a delegate the companion calls (`for_delegate`), a goal milestone
that runs with no turn (`for_unattended`), and the minimal context of an undo or a screen
action (`for_action`). `DERIVATION` gives each `AgentContext` field one rule per kind:

- `Inherit`: copied from the parent context.
- `Given`: the operation's argument supplies it (`source` says where it comes from).
- `Reset`: the field's default, with the reason this kind of run does not get the parent's value.

The operations walk `dataclasses.fields(AgentContext)` through the table, so a field cannot
be dropped silently: a field with no row raises `UndeclaredDerivationError`, and the table
test fails first. Adding a field means adding one row.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any, Callable, Mapping

from ze_agents.errors import UndeclaredDerivationError
from ze_agents.park import ParkedLoop
from ze_agents.types import (
    AbortToken,
    AgentContext,
    ConductorState,
    IdentityBuilder,
    ProcedureInvocation,
    WriteGateState,
)


@dataclass(frozen=True)
class Inherit:
    """Copied from the parent context."""


@dataclass(frozen=True)
class Given:
    """Supplied by an argument of the operation."""

    source: str


@dataclass(frozen=True)
class Reset:
    """The field's default. `reason` says why this kind of run does not inherit it."""

    reason: str


Rule = Inherit | Given | Reset


@dataclass(frozen=True)
class FieldRule:
    subtask: Rule
    delegate: Rule
    unattended: Rule
    action: Rule


KINDS = ("subtask", "delegate", "unattended", "action")

_I = Inherit()

_NO_TURN = "an unattended run has no turn, so fetch_context never built it"
_NO_PARENT = "an undo or screen action runs with no turn context"
_FRESH = "every run starts its own list"
_BRIEF = "the delegate's brief carries the context it needs (phase 151)"
_NO_CLIENT = "an unattended run has no live client"


def _row(
    subtask: Rule, delegate: Rule, unattended: Rule, action: Rule | None = None
) -> FieldRule:
    return FieldRule(
        subtask=subtask,
        delegate=delegate,
        unattended=unattended,
        action=action if action is not None else Reset(_NO_PARENT),
    )


def _turn_note(why_delegate: str = _BRIEF) -> FieldRule:
    """A prompt note built by fetch_context: subtasks inherit it, nobody else gets it."""
    return _row(_I, Reset(why_delegate), Reset(_NO_TURN))


DERIVATION: Mapping[str, FieldRule] = {
    "session_id": _row(_I, _I, Given("the goal executor: goal:<id>"), Given("caller")),
    "prompt": _row(
        Given("the subtask prompt"),
        Given("the assembled delegate brief"),
        Given("the milestone prompt"),
        Given("for_action: the empty prompt, an undo or screen action asks nothing"),
    ),
    "memory": _row(_I, _I, Reset(_NO_TURN)),
    "contacts": _row(_I, _I, Reset(_NO_TURN)),
    "tool_calls": _row(
        Reset(_FRESH), Reset(_FRESH), Reset(_FRESH), Reset(_FRESH)
    ),
    "messages": _row(
        Given("the first message of the turn (an image turn builds its own)"),
        Given("the delegate brief as the only message"),
        Reset("a milestone is one prompt with no history"),
    ),
    "persona": _row(_I, _I, Reset(_NO_TURN)),
    "model": _row(
        Given("the subtask's routed model"),
        Reset("the specialist runs on its own model, not the caller's"),
        Reset("the agent runs on its own model"),
    ),
    "reporter": _row(
        Given("runtime handles"), _I, Reset(_NO_CLIENT)
    ),
    "identity_builder": _row(
        Given("runtime handles"), _I, Reset(_NO_CLIENT)
    ),
    "abort_token": _row(Given("runtime handles"), _I, Reset(_NO_CLIENT)),
    "memory_store": _row(
        _I, _I, Given("the goal executor's memory store")
    ),
    "embed_fn": _row(
        Given("runtime handles"), _I, Reset(_NO_CLIENT)
    ),
    "token_sink": _row(
        Given("runtime handles (single-agent path only)"),
        Reset(
            "the specialist's tokens must not stream into the companion's reply"
        ),
        Reset(_NO_CLIENT),
    ),
    "tool_sink": _row(Given("runtime handles"), _I, Reset(_NO_CLIENT)),
    "script_runner": _row(
        Given("runtime handles"),
        _I,
        Reset("unattended runs have no script runner"),
    ),
    "sources": _row(
        Reset("citations are collected per run and merged upward after it"),
        Reset("the delegate merges its sources into the caller after the run"),
        Reset("citations are collected per run"),
    ),
    "screen_context_note": _turn_note(),
    "preset_note": _turn_note(),
    "resume_recap": _turn_note(),
    "open_priorities_note": _turn_note(),
    "preset": _turn_note(),
    "active_skills": _row(
        _I,
        Reset("the specialist uses its own tools; skills narrow the companion's"),
        Reset(_NO_TURN),
    ),
    "skill_tool_names": _row(
        _I,
        Reset("the specialist uses its own tools; skills narrow the companion's"),
        Reset(_NO_TURN),
    ),
    "procedure_guidance": _row(
        _I,
        Reset("the specialist does not invoke the companion's procedures"),
        Reset(_NO_TURN),
    ),
    "procedure_matches": _row(
        _I,
        Reset("the specialist does not invoke the companion's procedures"),
        Reset(_NO_TURN),
    ),
    "procedure_invocation": _row(
        Given("the turn state: this subtask's invocation, if any"),
        Reset("the procedure's tool narrowing belongs to the companion"),
        Reset(_NO_TURN),
    ),
    "conductor": _row(
        Given("the turn state: this subtask's ledger and the shared tally"),
        Reset(
            "a delegate cannot delegate (depth 1), and the companion's deadline stays with the companion"
        ),
        Reset(_NO_TURN),
    ),
    "write_gate": _row(
        Given(
            "the turn: Retry mode, pre-approved writes, this subtask's resume inputs"
        ),
        _I,
        Given("the milestone's pre-approved writes and held resume; no Retry"),
        Reset("run_action sets the request id and the loop flag itself"),
    ),
    "extensions": _row(
        _I,
        _I,
        Given("the goal executor: goal_id"),
    ),
    "timezone": _row(
        _I, _I, Given("application settings"), Reset(_NO_PARENT)
    ),
}


@dataclass(frozen=True)
class RuntimeHandles:
    """Live objects a context carries. Never checkpointed."""

    reporter: Any = None
    identity_builder: IdentityBuilder | None = None
    abort_token: AbortToken | None = None
    embed_fn: Callable[[str], Any] | None = None
    token_sink: Any | None = None
    tool_sink: Any | None = None
    script_runner: Any | None = None


@dataclass(frozen=True)
class ChildRunOutcome:
    """What a child run hands back besides its `AgentResult`."""

    index: int
    conductor: ConductorState
    procedure: ProcedureInvocation | None


def _rule(name: str, kind: str) -> Rule:
    row = DERIVATION.get(name)
    if row is None:
        raise UndeclaredDerivationError(
            f"AgentContext.{name} has no row in DERIVATION "
            "(declare how each kind of child run gets it)"
        )
    return getattr(row, kind)


def _inherited(name: str, parent: AgentContext) -> Any:
    value = getattr(parent, name)
    if name == "extensions":
        return dict(value)
    if name == "write_gate":
        return replace(value)
    return value


def _build(kind: str, parent: AgentContext | None, given: dict[str, Any]) -> AgentContext:
    kwargs: dict[str, Any] = {}
    for f in fields(AgentContext):
        rule = _rule(f.name, kind)
        if isinstance(rule, Inherit):
            if parent is None:
                raise UndeclaredDerivationError(
                    f"AgentContext.{f.name} is inherited by a {kind} run that has no parent"
                )
            kwargs[f.name] = _inherited(f.name, parent)
        elif isinstance(rule, Given):
            if f.name not in given:
                raise UndeclaredDerivationError(
                    f"AgentContext.{f.name} is declared Given for a {kind} run "
                    f"({rule.source}) but the operation did not supply it"
                )
            kwargs[f.name] = given[f.name]
    ctx = AgentContext(**kwargs)
    # Only a run's own loop sets the flag; no derivation hands it on.
    ctx.write_gate = replace(ctx.write_gate, loop_active=False)
    return ctx


def for_subtask(
    turn: AgentContext,
    *,
    prompt: str,
    model: str | None,
    messages: list[dict],
    runtime: RuntimeHandles,
    gate: WriteGateState,
    conductor: ConductorState,
    procedure: ProcedureInvocation | None,
) -> AgentContext:
    """A routed specialist or one subtask of a compound turn, from the turn context."""
    return _build(
        "subtask",
        turn,
        {
            "prompt": prompt,
            "model": model or None,
            "messages": messages,
            "reporter": runtime.reporter,
            "identity_builder": runtime.identity_builder,
            "abort_token": runtime.abort_token,
            "embed_fn": runtime.embed_fn,
            "token_sink": runtime.token_sink,
            "tool_sink": runtime.tool_sink,
            "script_runner": runtime.script_runner,
            "write_gate": gate,
            "conductor": conductor,
            "procedure_invocation": procedure,
        },
    )


def for_delegate(
    caller: AgentContext, *, prompt: str, resume: ParkedLoop | None
) -> AgentContext:
    """The specialist the companion delegates to. `resume` re-enters its parked loop."""
    ctx = _build(
        "delegate",
        caller,
        {"prompt": prompt, "messages": [{"role": "user", "content": prompt}]},
    )
    ctx.write_gate = replace(ctx.write_gate, resume=resume)
    depth = int(caller.extensions.get("_delegate_depth", 0) or 0)
    ctx.extensions["_delegate_depth"] = depth + 1
    return ctx


def for_unattended(
    *,
    session_id: str,
    prompt: str,
    timezone: str,
    memory_store: Any,
    extensions: dict[str, str | int | float | bool | None],
    pre_approved: frozenset[str],
    resume: WriteGateState | None = None,
) -> AgentContext:
    """A goal milestone: no turn, no live client, no Retry."""
    gate = replace(
        resume or WriteGateState(),
        pre_approved=frozenset(pre_approved),
        retry_mode=False,
    )
    return _build(
        "unattended",
        None,
        {
            "session_id": session_id,
            "prompt": prompt,
            "timezone": timezone,
            "memory_store": memory_store,
            "extensions": dict(extensions),
            "write_gate": gate,
        },
    )


def for_action(session_id: str) -> AgentContext:
    """The minimal context of an undo or a screen action. Only the session id."""
    return _build("action", None, {"session_id": session_id, "prompt": ""})


def outcome_of(ctx: AgentContext, index: int) -> ChildRunOutcome:
    """Read a child run's outcome from its context, also after the run parked."""
    conductor = replace(
        ctx.conductor,
        ledger=[dict(entry) for entry in ctx.conductor.ledger],
        stalls=dict(ctx.conductor.stalls),
    )
    procedure = (
        replace(ctx.procedure_invocation, subtask=index)
        if ctx.procedure_invocation is not None
        else None
    )
    return ChildRunOutcome(index=index, conductor=conductor, procedure=procedure)
