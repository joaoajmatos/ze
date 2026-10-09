# Data Model: Response Feedback and Retry

## Shared types (ze-agents / ze-plugin)
- `ClaimKind.FEEDBACK_RECORD = "feedback_record"`; licensed only to `SourceFunction.PERCEPTION` (alongside `FACT`). No other function gains it; Perception gains nothing else.
- `ToolReversibility`: `REVERSIBLE`, `IRREVERSIBLE`. `ToolSpec` gains `reversibility`, `undo_tool`, `undo_note`, `effect_phrase`.
- `Contribution.feedback_record: FeedbackRecordDraft | None` beside `action_record`.

## FeedbackRecord (ze-memory)
```python
class FeedbackKind(StrEnum): THUMBS_UP, THUMBS_DOWN, CLEARED, RETRY_REQUESTED

@dataclass(frozen=True)
class FeedbackRecord:
    id: UUID
    idempotency_key: str
    message_id: UUID          # assistant message rated
    thread_id: str
    kind: FeedbackKind
    occurred_at: datetime
    provenance: Provenance    # prompt_supplied
    confidence: Confidence    # 1.0
    target_face: TargetFace   # WORLD
    trace_present: bool
```
## Table `feedback_records` (`zm024`)
| Column | Type / constraint |
|---|---|
| id | UUID PK |
| idempotency_key | TEXT NOT NULL UNIQUE |
| message_id | UUID NOT NULL, index (message_id, occurred_at DESC) |
| thread_id | TEXT NOT NULL |
| kind | TEXT NOT NULL CHECK in the 4 values |
| occurred_at | TIMESTAMPTZ NOT NULL |
| provenance | TEXT NOT NULL doctrine CHECK |
| confidence | DOUBLE PRECISION NOT NULL CHECK 0..1 |
| target_face | TEXT NOT NULL doctrine CHECK |
| trace_present | BOOLEAN NOT NULL |
| created_at | TIMESTAMPTZ NOT NULL |
Invariants: (1) append-only, no update/delete API; (2) no message content, no free text; (3) message must exist, be `assistant`, at write time; (4) current rating = latest rating-kind row; (5) the retry link lives on `messages`, not on the feedback row; (6) never projected into `memory_facts`.

## `messages` additions (`zc031`, ze-core chain, down_revision `zc030`)
`replaces UUID NULL`, `replaced_by UUID NULL`, both indexed; invariant: `replaced_by` set only after the replacement is saved.

## Trace additions (JSONB, no migration)
`ToolCallTrace`: `access` (`read|write|unknown`), `reversibility` (`reversible|irreversible|null`), `undo_tool`, `gate` (`none|approved|denied|expired`), `effect_phrase`. `MessageTrace.effects_known: bool` (default False when absent).

## Derived read models
`RetryEligibility(available, reason_code, reason_text, actions[])`; `FeedbackView(current, history[], retry, replaces, replaced_by)`.
