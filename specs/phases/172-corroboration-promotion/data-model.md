# Data Model: Corroboration Promotion (172)

## Table `open_loop_sources` (migration `zw003`, ze-worldstate)

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `UUID` | no | `DEFAULT gen_random_uuid()`, PK |
| `loop_id` | `UUID` | no | `REFERENCES open_loops(id) ON DELETE CASCADE` |
| `role` | `TEXT` | no | `CHECK (role IN ('origin','corroboration'))` |
| `inflow` | `TEXT` | no | `conversation`, `email`, `calendar`, `ingestion` (not a CHECK: plugin inflows are open strings, as `open_loops.provenance`) |
| `source_ref` | `TEXT` | no | thread id, Gmail thread or message id, calendar `external_ref`, ingestion id |
| `evidence_kind` | `TEXT` | yes | e.g. `episode`, `ingestion`; NULL for calendar |
| `evidence_id` | `UUID` | yes | |
| `same_concern` | `DOUBLE PRECISION` | yes | Noul score; NULL for `origin` |
| `promoted` | `BOOLEAN` | no | `DEFAULT false` |
| `model` | `TEXT` | yes | reported System One model id |
| `latency_ms` | `INTEGER` | yes | |
| `created_at` | `TIMESTAMPTZ` | no | `DEFAULT now()` |

Constraints and indexes:
- `UNIQUE (loop_id, inflow, source_ref)`
- `INDEX open_loop_sources_loop_idx (loop_id, created_at)`
- `INDEX open_loop_sources_key_idx (inflow, source_ref)` (dropped-loop lookups)

Downgrade drops the table. No change to `open_loops`.

## Types (`ze_worldstate/types.py`)

```python
@dataclass(frozen=True)
class SourceKey:
    inflow: str
    ref: str

class LoopSourceRole(StrEnum):
    ORIGIN = "origin"
    CORROBORATION = "corroboration"

@dataclass
class LoopSource:
    loop_id: UUID
    role: LoopSourceRole
    key: SourceKey
    evidence: EvidenceRef | None = None
    same_concern: float | None = None
    promoted: bool = False
    model: str | None = None
    latency_ms: int | None = None
    id: UUID | None = None
    created_at: datetime | None = None
```

## Judge types (`ze_worldstate/corroboration_judge.py`)

```python
Q_SAME = "same_concern"

@dataclass(frozen=True)
class CorroborationSurfaceConfig:
    enabled: bool = False
    corroborate_hold: float | None = None
    promote_hold: float | None = None
    # calibrated: enabled and both set and corroborate_hold <= promote_hold

CorroborationKind = Literal["promote", "corroborate", "not_same", "fallback"]

@dataclass(frozen=True)
class CorroborationDecision:
    kind: CorroborationKind
    reason: str
    score: float | None = None
```

## `LoopStore` Protocol additions (`ze_worldstate/store.py`)

| Method | Behavior |
|---|---|
| `add_source(source: LoopSource) -> LoopSource \| None` | `INSERT ... ON CONFLICT (loop_id, inflow, source_ref) DO NOTHING RETURNING *`; `None` on conflict |
| `list_sources(loop_id) -> list[LoopSource]` | ordered by `created_at` |
| `list_sources_for(loop_ids) -> dict[UUID, list[LoopSource]]` | one query (`loop_id = ANY($1)`), for the REST list |
| `promote(loop_id, *, confidence, window_days) -> OpenLoop \| None` | guarded single UPDATE (research R7); `None` when not `suspected` |
| `mark_source_promoted(source_id) -> None` | `UPDATE open_loop_sources SET promoted = true WHERE id = $1` |

`set_confidence` (exists) is reused for the corroborate step.

## Loop state transitions touched

| From | To | Trigger | New? |
|---|---|---|---|
| `suspected` | `suspected` (confidence up) | corroborate | yes |
| `suspected` | `active` | promote (guarded) | new trigger, existing edge |

No other transition changes.

## Calibration row (`eval/calibration/corroboration*.jsonl`)

```json
{"id": "t-en-001", "lang": "en", "loop_title": "Sort out the deposit with the landlord",
 "loop_inflow": "conversation", "inflow": "email",
 "text": "Reminder: the deposit return form is still missing your signature.",
 "new_title": "Sign the deposit return form", "gold_same": true, "kind": "paraphrase"}
```

`kind` ∈ `same`, `paraphrase`, `cross_lingual`, `same_entity_other`, `same_topic_other`, `unrelated`. `gold_same` is true only for the first three.

## REST schemas (`apps/ze-api/ze_api/api/schemas.py`)

```python
class LoopListItem(BaseModel):   # existing; add:
    promoted: bool
    source_inflows: list[str]

class LoopSourceItem(BaseModel):  # new
    role: str
    inflow: str
    evidence_kind: str | None
    same_concern: float | None
    promoted: bool
    created_at: str | None

class LoopDetail(LoopListItem):  # existing; add:
    sources: list[LoopSourceItem]
```

`source_ref` is not exposed (internal ids; the evidence list already shows what the user can read).
