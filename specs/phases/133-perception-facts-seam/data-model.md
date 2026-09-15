# Data Model: Perception Facts onto the Contribution Seam

No new tables. This phase changes in-process envelopes and citations on existing `Fact` rows.

## Perception-fact contribution

In-process only. Built by `fact_to_contribution`.

| Field | Value this phase |
|---|---|
| `claim_kind` | Always `ClaimKind.FACT` |
| `provenance` | `SYNTHESIZED` or `PROMPT_SUPPLIED` (per fact) |
| `confidence` | From `Fact.confidence` + existing decay profile used by signals (`TIME_LINEAR`) unless a caller already carries a `Confidence` |
| `target_face` | `USER` (conversation, inbound, onboarding, goal-learning); `WORLD` (ingestion) |
| `source_function` | Always `SourceFunction.PERCEPTION` |
| `evidence` | `[]` or citation refs (`ingestion` / `goal`) |
| `content` | `"{predicate} {value}"` (or equivalent non-empty text for collision scan) |
| `entity_ids` | `[]` unless already resolved on the `Fact` (`subject_id` / `object_id` when present) |

## Domain `Fact` (unchanged schema)

Existing `ze_memory.types.Fact`. This phase MAY set:

- `source_refs`: append ingestion or goal UUID
- `reviewed`: stay `True` for onboarding seeds
- `agent`: unchanged from today’s callers

MUST NOT set `provenance="synthesized"` solely because the Contribution is `SYNTHESIZED` (research R2).

## `EvidenceRef` (extended)

Existing dataclass in `ze_plugin.contribution`.

| Field | Change |
|---|---|
| `kind` | Add `"ingestion"` and `"goal"` to the `Literal` |
| `id` | UUID of ingest run or goal |

Validation rules:

- `FACT` still does not *require* evidence.
- `fact` / `episode` / `signal` dangling checks unchanged when checkers are provided.
- `ingestion` / `goal`: skip dangling unless an optional checker is passed.

## Persist callback

`write` inserts via existing `memory_facts` INSERT (including today’s `claim_kind` column derived from the **string** `Fact.provenance`, still `"raw"` → `FACT`). Returns inserted UUID.

## Out of model

- `memory_facts.provenance` column / shared `Provenance` enum on the row → Phase 134
- Collision log schema → already Phase 126
- Priority / loop / recap types → unchanged
