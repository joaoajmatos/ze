# Contract: Action Records

Internal Python contract. This phase adds no REST or WebSocket frame.

## Contribution contract hard cut

```python
class ClaimKind(StrEnum):
    ACTION_RECORD = "action_record"

_LICENSE[SourceFunction.ACTION] = frozenset({ClaimKind.ACTION_RECORD})
```

`Contribution` gains an optional, typed action payload only for
`claim_kind=ACTION_RECORD`:

```python
@dataclass
class Contribution:
    # existing claim metadata
    action_record: ActionRecordDraft | None = None
```

Validation MUST reject an ACTION_RECORD without `action_record`, and reject an
`action_record` payload paired with any other kind. It MUST retain current license and evidence
validation. This is a hard replacement for the empty ACTION license; there is no transitional
allow-list.

## Submission API

```python
@dataclass(frozen=True)
class ActionRecordDraft:
    idempotency_key: str
    action_type: str
    actor: str
    producer_plugin: str
    lifecycle: ActionLifecycle
    outcome: ActionOutcome | None
    occurred_at: datetime
    summary: str
    authoritative_ref: AuthoritativeRef
    context: ActionContext = field(default_factory=ActionContext)
    causal_refs: list[CausalRef] = field(default_factory=list)
    retry_of: UUID | None = None
    supersedes: UUID | None = None
    failure_code: str | None = None

class ActionRecordStore(Protocol):
    async def append(self, contribution: Contribution) -> ActionRecord: ...
    async def get(self, record_id: UUID) -> ActionRecord | None: ...
    async def list(
        self,
        *,
        authoritative_ref: AuthoritativeRef | None = None,
        causal_ref: CausalRef | None = None,
        before: datetime | None = None,
        limit: int = 100,
    ) -> list[ActionRecord]: ...
```

The public producer entry point is:

```python
async def submit_action_record(
    store: ActionRecordStore,
    contribution: Contribution,
) -> ActionRecord: ...
```

It calls the existing validated contribution path, with `store.append` as `write=`.
No producer can call an unvalidated insert method. The implementation may use a private
`_append` beneath the store facade.

## Required stamps

| Field | Required value |
|---|---|
| `source_function` | `SourceFunction.ACTION` |
| `claim_kind` | `ClaimKind.ACTION_RECORD` |
| `provenance` | Existing doctrine provenance honestly selected by the producer |
| `confidence` | Existing shared `Confidence`; must express outcome certainty |
| `target_face` | Domain-appropriate existing `TargetFace` |
| `action_record` | Non-null valid `ActionRecordDraft` |
| `action_record.actor` | Non-empty agent, job, or system actor identifier |
| `action_record.producer_plugin` | Non-empty plugin/core producer identifier |

## Idempotency and errors

- `append` MUST atomically insert or return the row bearing `idempotency_key`.
- An existing key with a materially different draft MUST raise a typed `ZeError`; it must not
  silently reuse or overwrite the prior evidence.
- `retry_of` / `supersedes` must point to existing ActionRecords; dangling ids fail before
  persist.
- Invalid lifecycle/outcome combinations, a missing authoritative reference, unsafe summaries,
  or a dangling required reference raise typed `ZeError` before append.
- `ActionContext` stores only available request/correlation identifiers. Its keys are typed and
  known to the shared contract; it does not accept an unbounded plugin payload.
- A transient persistence failure is surfaced to the producer/handoff worker. It is retryable
  with the unchanged key. It never causes automatic replay of the original side effect.

## Producer adapter boundary

Each source domain exposes a narrow adapter that receives an already persisted source record:

```python
async def record_workspace_run(run: WorkspaceRun) -> ActionRecord: ...
async def record_outbound_message(sent: SentMessage) -> ActionRecord: ...
```

Adapters select the source's `authoritative_ref`, stable action type, lifecycle/outcome,
sanitized summary, and causal refs. They MUST NOT copy raw command arguments, recipient/message
body, credentials, or raw stack traces. Calendar/workflow/goal adapters are follow-on producers.

## Explicit exclusions

- No `MemoryStore` fact-write method accepts ActionRecord.
- No `Fact`, `Signal`, `OpenLoop`, or `signal_sources()` type changes.
- No arbitration resolver, collision winner selection, REST endpoint, or UI contract.
