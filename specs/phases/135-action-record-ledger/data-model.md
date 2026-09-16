# Data Model: Action Record Ledger

## Shared doctrine types

| Type | Change |
|---|---|
| `ClaimKind` | Add closed member `ACTION_RECORD = "action_record"` |
| `SourceFunction.ACTION` license | `frozenset({ClaimKind.ACTION_RECORD})` |
| `Provenance`, `Confidence`, `TargetFace` | Reuse unchanged shared types |
| `EvidenceRef.kind` | Add `"action_record"` with UUID validation via ActionRecordStore |

`ACTION_RECORD` is only licensed to Action. No other source function gains this kind, and Action
does not gain any existing claim kind.

## `ActionRecord`

```python
@dataclass(frozen=True)
class AuthoritativeRef:
    domain: str
    record_id: str

@dataclass(frozen=True)
class CausalRef:
    kind: Literal["fact", "episode", "signal", "goal", "workflow", "open_loop",
                  "approval", "action_record"]
    id: UUID | str

@dataclass(frozen=True)
class ActionContext:
    request_id: UUID | None = None
    session_id: UUID | None = None
    message_id: UUID | None = None
    thread_id: UUID | None = None
    goal_id: UUID | None = None
    milestone_id: UUID | None = None
    workflow_id: UUID | None = None
    workflow_run_id: UUID | None = None
    workspace_run_id: UUID | None = None
    channel_id: UUID | None = None
    outreach_id: UUID | None = None
    calendar_ref: str | None = None
    reminder_id: UUID | None = None

@dataclass(frozen=True)
class ActionRecord:
    id: UUID
    idempotency_key: str
    action_type: str
    actor: str
    producer_plugin: str
    lifecycle: ActionLifecycle
    outcome: ActionOutcome | None
    occurred_at: datetime
    provenance: Provenance
    confidence: Confidence
    target_face: TargetFace
    summary: str
    authoritative_ref: AuthoritativeRef
    context: ActionContext
    evidence: list[EvidenceRef]
    causal_refs: list[CausalRef]
    retry_of: UUID | None
    supersedes: UUID | None
    failure_code: str | None
```

`ActionLifecycle` is a closed string enum: `started`, `in_progress`, `succeeded`, `failed`,
`cancelled`, `partial`, `timed_out`, `unknown`.

`ActionOutcome` is a closed string enum: `success`, `failure`, `cancelled`, `partial`,
`timeout`, `unknown`. It is required for terminal lifecycle states and absent for `started` /
`in_progress`.

## `action_records` table

Owned by `core/cognition/ze-memory`, with the next available `zm` migration revision.

| Column | Type / constraint | Meaning |
|---|---|---|
| `id` | UUID PK | Ledger-record identity |
| `idempotency_key` | TEXT NOT NULL UNIQUE | Logical observation deduplication |
| `action_type` | TEXT NOT NULL | Stable producer-owned action label |
| `actor` | TEXT NOT NULL | Agent, job, or system actor that attempted the action |
| `producer_plugin` | TEXT NOT NULL | Plugin or core package that owns the producer |
| `lifecycle` | TEXT NOT NULL CHECK | Immutable observed state |
| `outcome` | TEXT nullable CHECK | Required iff lifecycle is terminal |
| `occurred_at` | TIMESTAMPTZ NOT NULL | When observation occurred |
| `provenance` | TEXT NOT NULL doctrine CHECK | Honest epistemic origin |
| `confidence` | DOUBLE PRECISION NOT NULL CHECK 0–1 | Confidence in observed outcome |
| `target_face` | TEXT NOT NULL doctrine CHECK | Affected world-state face |
| `summary` | TEXT NOT NULL | Bounded, sanitized description |
| `authoritative_domain` | TEXT NOT NULL | Source-owner namespace |
| `authoritative_record_id` | TEXT NOT NULL | Opaque source-row identity |
| `context` | JSONB NOT NULL DEFAULT `{}` | Available request and correlation identifiers |
| `evidence` | JSONB NOT NULL DEFAULT `[]` | Typed contribution evidence |
| `causal_refs` | JSONB NOT NULL DEFAULT `[]` | Typed causal links |
| `retry_of` | UUID nullable FK action_records | Earlier attempted record |
| `supersedes` | UUID nullable FK action_records | Corrected observation |
| `failure_code` | TEXT nullable | Bounded sanitized failure classification |
| `created_at` | TIMESTAMPTZ NOT NULL | Append timestamp |

Indexes: descending `occurred_at`; `(authoritative_domain, authoritative_record_id,
occurred_at DESC)`; GIN indexes for reference query only if JSONB query profiling warrants one.

## Invariants

1. Exactly one `AuthoritativeRef` is present.
2. `idempotency_key` identifies one immutable observation, not an entire retry chain.
3. A `retry_of` or `supersedes` id must exist and cannot equal `id`.
4. No ordinary update/delete API exists. Migration/admin repair is exceptional and documented.
5. `summary` and `failure_code` cannot contain secrets, raw command input, message body, or
   unbounded output.
6. `actor` and `producer_plugin` are non-empty producer-owned strings; plugin names are never
   elevated into a closed core enum.
7. No row projects into `memory_facts`, fact embeddings, fact contradiction, or fact review.

## Lifecycle transition representation

The table does not enforce transitions by update. Producers append observations consistent with:

```text
started → in_progress → succeeded | failed | cancelled | partial | timed_out | unknown
```

An observation may begin at any truthful known state (for example, an existing completed source
record backfilled during a producer cutover). A later correction is a new row with
`supersedes`, never an edit.
