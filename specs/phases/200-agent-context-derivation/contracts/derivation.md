# Contract: AgentContext derivation and state lifetimes

**Phase**: 200. These are in-process Python interfaces. REST, WS and the stored `MessageTrace` JSON do not change.

## `ze_agents.derive` (new; ze-agents)

```python
@dataclass(frozen=True)
class Inherit: ...
@dataclass(frozen=True)
class Given:
    source: str          # where the operation's argument comes from
@dataclass(frozen=True)
class Reset:
    reason: str          # why this kind of run does not get the parent's value

@dataclass(frozen=True)
class FieldRule:
    subtask: Inherit | Given | Reset
    delegate: Inherit | Given | Reset
    unattended: Inherit | Given | Reset
    action: Inherit | Given | Reset

DERIVATION: Mapping[str, FieldRule]      # one row per AgentContext field (data-model.md)
KINDS = ("subtask", "delegate", "unattended", "action")

@dataclass(frozen=True)
class RuntimeHandles:
    reporter: Any = None
    identity_builder: IdentityBuilder | None = None
    abort_token: AbortToken | None = None
    embed_fn: Callable[[str], Any] | None = None
    token_sink: Any | None = None
    tool_sink: Any | None = None
    script_runner: Any | None = None

@dataclass(frozen=True)
class ChildRunOutcome:
    index: int
    conductor: ConductorState
    procedure: ProcedureInvocation | None

def for_subtask(turn: AgentContext, *, prompt: str, model: str | None,
                messages: list[dict], runtime: RuntimeHandles,
                gate: WriteGateState, conductor: ConductorState,
                procedure: ProcedureInvocation | None) -> AgentContext: ...

def for_delegate(caller: AgentContext, *, prompt: str,
                 resume: ParkedLoop | None) -> AgentContext: ...

def for_unattended(*, session_id: str, prompt: str, timezone: str,
                   memory_store: Any, extensions: dict[str, str | int | float | bool | None],
                   pre_approved: frozenset[str],
                   resume: WriteGateState | None = None) -> AgentContext: ...

def for_action(session_id: str) -> AgentContext: ...

def outcome_of(ctx: AgentContext, index: int) -> ChildRunOutcome: ...
```

Guarantees:
- Each operation builds its kwargs from `dataclasses.fields(AgentContext)` and `DERIVATION[field.name].<kind>`. It never lists fields by hand.
- A field missing from `DERIVATION` raises `UndeclaredDerivationError(field)`.
- `Inherit` on `extensions` copies the dict. `for_delegate` adds `_delegate_depth = parent depth + 1`. Mutating a child's `extensions` never changes the parent's.
- `Inherit` on `write_gate` (delegate) returns a new `WriteGateState` with `resume` = the argument and `loop_active=False`.
- Every operation returns `loop_active=False`.
- `outcome_of` copies `ctx.conductor` (keeping the shared `tally` object) and stamps `procedure.subtask = index`.

## `ze_agents.lifetime` (new; ze-agents, re-exported from `ze_sdk.types`)

```python
@dataclass(frozen=True)
class Turn:
    reset: Any = None                       # immutable values only
    factory: Callable[[], Any] | None = None  # list / dict for mutable resets
    def value(self) -> Any: ...
@dataclass(frozen=True)
class Input: ...
@dataclass(frozen=True)
class Thread:
    reason: str
@dataclass(frozen=True)
class Run:
    reason: str

Lifetime = Turn | Input | Thread | Run

def field_lifetimes(td: type) -> dict[str, Lifetime]: ...   # raises UndeclaredLifetimeError
def turn_reset(*tds: type) -> dict[str, Any]: ...           # fresh value per call
```

Usage on a `TypedDict` field: `judgments: Annotated[list, Turn(factory=list)]`.

Guarantees:
- `field_lifetimes` reads `get_type_hints(td, include_extras=True)` on the class that declares the fields and takes the first lifetime marker in the `Annotated` metadata.
- An unannotated field raises `UndeclaredLifetimeError`, which names the class and field.
- `turn_reset` returns a new list or dict on every call, so two turns never share one.

## ze-core changes to existing interfaces

| Symbol | Before | After |
|---|---|---|
| `make_graph_input(raw, session_id)` | hand-kept 38-key dict | `make_graph_input(raw, session_id, state_type=AgentState)` = `turn_reset(state_type)` plus the `Input` keys from `raw` |
| `build_state_type(plugins)` | merges the TypedDicts | also validates `AgentState` and each extension through `field_lifetimes`; raises `UndeclaredLifetimeError` |
| new `with_turn_reset(node, state_type)` (`orchestration/state.py`) | — | wraps a node so its updates start from `turn_reset(state_type)` (workflow step) |
| `Container.state_type` (`ze_core/container.py`) | — | `type`, default `AgentState`; set by both graph builders |
| new `orchestration/child_runs.py` | — | `runtime_handles(config, *, stream)`, `gate_input(turn, state, config, index)`, `conductor_input(state, index, tally)`, `tally_from(state)`, `procedure_input(state, index)`, `merge_outcomes(state, outcomes, tally) -> dict`, `turn_ledger(state) -> list[dict]` |
| `_run_with_timeout(...)` | returns `AgentResult \| ParkedSubtask` | returns `(AgentResult \| ParkedSubtask, ChildRunOutcome)` |
| `procedure_usage_trace(ctx)` | reads the context | `procedure_usage_trace(state)` reads `procedure_invocations[0]` |
| `complete_procedure_invocation(ctx, result, config)` | one invocation | `complete_procedure_invocations(state, config)`: each invocation with its own subtask's result |
| `record_guided_actions(ctx, result, config)` | single path only | called per finished subtask with that subtask's invocation |
| `AgentState.conductor_ledger` | `list` | `conductor_ledgers: list[list[dict]]` |
| `AgentState.procedure_matches` | written, never read | deleted |
| new `AgentState.procedure_invocations` | — | `list[ProcedureInvocation]` |

ze-api: `begin_workflow_turn(workflow, state_type)`; `build_workflow_graph` registers `with_turn_reset(load_workflow_step, state_type)`; `ui_actions._context` calls `for_action`.

ze-automation: `_execute_milestone` calls `for_unattended`. `_HeldResume.context_kwargs()` becomes `_HeldResume.gate()`, which returns a `WriteGateState`.

## Errors (`ze_agents/errors.py`)

- `UndeclaredDerivationError(ZeError)`: an `AgentContext` field has no `DERIVATION` row.
- `UndeclaredLifetimeError(ZeError)`: a state `TypedDict` field has no lifetime marker. Re-exported from `ze_sdk.errors`.

## Unchanged surfaces

- REST `GET /api/v0/messages/{id}/trace`: `conductor_hint`, `conductor_ledger` (the flattened ledgers), `procedure`.
- The WS `trace_update` frame.
- The stored `MessageTrace` JSON.
- `make_graph_input_from_raw_text`.
