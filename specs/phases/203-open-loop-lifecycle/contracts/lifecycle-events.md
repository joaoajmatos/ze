# Contract: `LoopLifecycle` (ze_worldstate/lifecycle)

The one write surface for open loops. The contract step (lane `lead`, T001–T003) lands these signatures, the rules table and the errors before any other lane starts. Bodies may raise `NotImplementedError` until lane `lead` fills them in; callers code and test against `AsyncMock(spec=LoopLifecycle)`.

Rules per event: data-model.md, "Events and rules". Transactions and guards: research R2.

```python
# ze_worldstate/lifecycle/rules.py — pure, no I/O
class LoopEvent(StrEnum):
    CREATE_SUSPECTED = "create_suspected"
    CREATE_DECLARED = "create_declared"
    CONFIRM = "confirm"
    TRACK = "track"
    NOTE_EVIDENCE = "note_evidence"
    CORROBORATE = "corroborate"
    PROMOTE = "promote"
    RESOLVE = "resolve"
    CLOSE = "close"
    DROP = "drop"
    EXPIRE = "expire"
    LINK = "link"
    DECAY = "decay"
    DRIFT = "drift"

class Verdict(StrEnum):          # what an event does from one starting state
    MOVE = "move"                # to EventRule.to_state
    STAY = "stay"                # writes, state unchanged
    NO_CHANGE = "no_change"      # returns without writing or raising
    REFUSED = "refused"          # raises InvalidLoopTransitionError

@dataclass(frozen=True)
class EventRule:
    event: LoopEvent
    verdicts: Mapping[LoopState, Verdict]   # every LoopState present (create events: none, see below)
    to_state: LoopState | None

EVENT_RULES: Mapping[LoopEvent, EventRule]

def verdict(event: LoopEvent, state: LoopState) -> Verdict: ...
def allowed_from(event: LoopEvent) -> tuple[LoopState, ...]:   # MOVE or STAY, for the SQL guard
    ...

class DeclaredStamp:
    CONFIDENCE: Final = 0.9
    DEFAULT_WINDOW_DAYS: Final = 7
    @staticmethod
    def sql(confidence_expr: str, window_param: str) -> str: ...   # the one fragment (R3)

SUSPECTED_CONFIDENCE: Final = 0.3
```

Create events have no starting state; `EVENT_RULES` lists them with an empty `verdicts` map and their `to_state`.

```python
# ze_worldstate/lifecycle/events.py
class LoopLifecycle:
    def __init__(
        self,
        pool: DBPool,
        *,
        memory_store: Any = None,      # existence checkers for the contribution seam
        collision_store: Any = None,   # set late by wire_collision_detection, as today
        nli_client: Any = None,
    ) -> None: ...

    # creates (contribution seam: the transaction is the writer callback, R5)
    async def create_suspected(self, draft: LoopDraft) -> OpenLoop: ...
    async def create_declared(self, draft: LoopDraft, *, window_days: int | None = None) -> OpenLoop: ...

    # user and agent events
    async def confirm(self, loop_id: UUID) -> OpenLoop: ...
    async def track(self, loop_id: UUID, *, window_days: int, entity_ids: Sequence[UUID] = ()) -> Tracked: ...
    async def close(self, loop_id: UUID) -> OpenLoop: ...
    async def drop(self, loop_id: UUID) -> OpenLoop: ...
    async def link(self, loop_id: UUID, *, reminder_id: UUID | None = None, goal_id: UUID | None = None) -> bool: ...

    # inflow events
    async def note_evidence(self, loop_id: UUID, *, evidence: Sequence[EvidenceRef], entity_ids: Sequence[UUID]) -> OpenLoop: ...
    async def corroborate(self, loop_id: UUID, corroboration: Corroboration) -> SourceWrite: ...
    async def promote(self, loop_id: UUID, corroboration: Corroboration) -> SourceWrite: ...
    async def resolve(self, loop_id: UUID, *, evidence: Sequence[EvidenceRef]) -> OpenLoop | None: ...

    # automatic events
    async def decay_from_evidence(self, evidence_type: str, evidence_id: UUID) -> list[OpenLoop]: ...
    async def drift(self, loop_id: UUID) -> OpenLoop | None: ...
    async def expire(self, loop_id: UUID) -> OpenLoop | None: ...
```

Value types live in `lifecycle/events.py` and are exported from the package, so `types.py` (which 202 also edits) gains nothing:

```python
@dataclass(frozen=True)
class LoopDraft:
    title: str
    provenance: str
    evidence: tuple[EvidenceRef, ...] = ()
    entity_ids: tuple[UUID, ...] = ()
    source: SourceKey | None = None

@dataclass(frozen=True)
class Corroboration:
    evidence: tuple[EvidenceRef, ...]
    entity_ids: tuple[UUID, ...]
    key: SourceKey
    same_concern: float
    confidence: float | None = None   # CORROBORATE: the raised value; PROMOTE: ignored
    model: str | None = None
    latency_ms: int | None = None

@dataclass(frozen=True)
class SourceWrite:
    outcome: Literal["corroborate", "promote", "duplicate_source", "lost_race"]
    loop: OpenLoop

@dataclass(frozen=True)
class Tracked:
    outcome: str        # TrackOutcome.CONFIRMED | REINFORCED | REVIVED
    loop: OpenLoop
```

## Behavior every method guarantees

- **Atomic**: one transaction; on any error nothing the event writes is kept (SC-001).
- **Returns the stored row**: the `OpenLoop` comes from `RETURNING *` (or a read in the same transaction), never patched in Python. The confirm REST response matches the row (US1 scenario 2).
- **Guarded by state**: the `WHERE` clause uses `allowed_from(event)`; a refused move raises `InvalidLoopTransitionError`, a missing loop `LoopNotFoundError`, a no-change race returns `None` / `False` (data-model.md).
- **Logs once**: `open_loop_<event>` with `loop_id`, `from_state`, `to_state` (the existing `open_loop_transitioned` and `open_loop_created` event names are replaced by these).
- **Never** writes a fingerprint on resolve; **always** writes one on drop and expire, in the same statement as the state change (FR-006).

## What the store keeps (`PostgresLoopStore`, `LoopStore` protocol)

`get`, `list`, `list_by_evidence`, `count_evidence_links`, `list_evidence`, `list_drift_candidates`, `list_sources`, `list_sources_for`. Nothing else (FR-007).
