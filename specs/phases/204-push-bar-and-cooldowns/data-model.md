# Data Model: Push Bar and Cooldowns

## Tables

### `push_log` (ze-proactive, changed by `zpro006`)

The governor's private claim table. One row per push the governor let through and still holds (`delivered` or `held`), whether discretionary or a cooldown claim.

| Column | Type | Notes |
|---|---|---|
| `id` | `SERIAL` PK | the claim id `release` deletes by |
| `event_type` | `TEXT NOT NULL` | the push kind's `event_type`; rows kept from before `zpro006` say `attention_push` |
| `claim_key` | `TEXT NOT NULL` | renamed from `idempotency_key`; the caller's `OncePer.key` |
| `discretionary` | `BOOLEAN NOT NULL` | true = counts against the daily budget and feeds novelty history |
| `payload` | `TEXT` | the push body (novelty history reads it) |
| `sent_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | claim time; windows are measured from it |

Indexes: `push_log_claim_key_sent_at_idx (claim_key, sent_at DESC)`; `push_log_discretionary_sent_at_idx (sent_at) WHERE discretionary`. Dropped: `ux_push_log_event_idempotency`, `push_log_event_type_sent_at_idx`.

Rules:

- A row exists only for a push whose outcome is `delivered` or `held` (or one still in flight). `failed` deletes it; `over_budget` never inserts it.
- Cooldown: a key is cooling when a row with that `claim_key` has `sent_at > now() - within`, or exists at all when `within` is `None`.
- Budget: `used` = discretionary rows with `sent_at > now() - 24 h`.
- Nothing outside ze-proactive reads or writes it (FR-008).

### `surfacing_memory` (ze-priority, new in `zpri002`)

`TurnSurfacing`'s record of what the conversation already raised.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL` PK | |
| `kind` | `TEXT NOT NULL CHECK (kind IN ('inline','offer'))` | inline mention, or resume offer |
| `source_kind` | `TEXT NOT NULL` | `loop` today |
| `source_id` | `UUID NOT NULL` | |
| `recorded_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

Index: `surfacing_memory_lookup_idx (source_kind, source_id, kind, recorded_at DESC)`. Rows older than 30 days are deleted by `record`.

### `workflow_executions` (ze-automation, read only)

No schema change. A failure is a row with `status = 'failed'`; `completed_at` is the failure time; `error` is the message.

## Value types

### `OncePer` (`ze_proactive/types.py`)

```python
@dataclass(frozen=True)
class OncePer:
    key: str
    within: timedelta | None = None  # None: once ever
```

Validation: `key` non-empty; `within`, when given, positive. Invalid values raise `PushPolicyError`.

### `PushOutcome` (`ze_proactive/types.py`)

`Literal["delivered", "held", "suppressed_budget", "deduped", "failed"]`. `duplicate` is removed.

`is_sent(outcome: PushOutcome | None) -> bool` is `outcome in ("delivered", "held")`.

### `ClaimResult` (`ze_proactive/push_log_store.py`, private)

```python
@dataclass(frozen=True)
class ClaimResult:
    status: Literal["won", "cooling", "over_budget"]
    claim_id: int | None  # set only when won
```

### `BarThresholds` (`ze_proactive/candidates.py`)

```python
@dataclass(frozen=True)
class BarThresholds:
    confidence: float
    relevance: float
    novelty_similarity_max: float
    grounding: float
    inline_cooldown_hours: float | None  # None: no conversation check
```

| Source | Config keys (unchanged) | Values on main |
|---|---|---|
| loop | `worldstate.push.thresholds.{tau_confidence, tau_relevance, novelty_similarity_max, grounding_threshold}`, `worldstate.push.inline_cooldown_hours` | 0.5, 0.5, 0.85, 0.3, 12 |
| hypothesis | `correlation.salience.surfacing.{tau_push, tau_relevance, novelty_similarity_max}`, NLI `nli_grounding_threshold` | 0.6, 0.5, 0.85, 0.30, `None` |

### `PushCandidate` (`ze_proactive/candidates.py`)

```python
@dataclass(frozen=True)
class PushCandidate:
    source_kind: str            # "loop" | "hypothesis" | a future kind
    source_id: UUID
    entity: Any                 # the source's record, for ranking and send
    body: str                   # the exact push body (novelty compares it)
    claim: str                  # the statement grounding checks
    confidence: float
    relevance: float
    evidence_labels: tuple[str, ...]
```

| Source | `body` | `claim` | `relevance` | `evidence_labels` |
|---|---|---|---|---|
| loop | `format_hedged_mention(title, drift_rationale)` | `title` (phase 170) | `RelevanceModel.score(...)` on the loop's entity names | evidence summaries |
| hypothesis | `f"{summary}\n\n{narrative}"` | `summary` | `hypothesis.relevance` | evidence ref labels |

### `BarVerdict` (`ze_priority/push_bar.py`)

```python
BarReason = Literal["low_confidence", "irrelevant", "mentioned_recently", "not_novel", "ungrounded"]

@dataclass(frozen=True)
class BarVerdict:
    candidate: PushCandidate
    passed: bool
    reason: BarReason | None  # None when passed
```

### `WorkflowFailure` (`ze_automation/workflow/types.py`)

```python
@dataclass(frozen=True)
class WorkflowFailure:
    workflow_id: UUID | None
    workflow_name: str        # "unknown" when the run has no workflow
    execution_id: UUID
    failed_at: datetime
    error: str | None
```

## State: a discretionary push

```text
notify(kind, once_per)
  └─ claim(key, within, discretionary)
       ├─ cooling      → "deduped"            (no notification row)
       ├─ over_budget  → row delivery=suppressed → "suppressed_budget"   (no claim)
       └─ won ── decide(quiet)
                 ├─ hold    → row delivery=held      → "held"        (claim kept; a failed release keeps it)
                 └─ deliver → push ok                → "delivered"   (claim kept)
                              push or persist error  → "failed"      (claim deleted)
```

An accountability push with `once_per` follows the same path without `over_budget`. A requested push takes no claim.
