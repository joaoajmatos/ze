# Data Model: Claim Honesty Fixes (199)

No new tables. One column is dropped. Three one-time data repairs run. One store method is added.

## Fact (`memory_facts`, ze-memory, `zm` chain)

| Field | Change |
|---|---|
| `provenance` | Perception writes (`write_memory`, ingestion sink, inbound processor) store `prompt_supplied` instead of `synthesized`. `synthesized` is written only by the dream promoter. |
| `claim_kind` | Unchanged for new writes (`fact` from perception, `inference` from the dream). The repair sets `fact` on re-stamped rows. |
| `dream_run_id` | Unchanged column. It becomes the marker that decay and expiry select on: a fact is a **dream insight** iff `dream_run_id IS NOT NULL`. |
| `creation_method` | Does not exist on this table. The promoter's insert stops naming it. |

**Invariant (FR-002)**: `provenance = 'synthesized'` ⇒ `dream_run_id IS NOT NULL`, after zm026 and for every new write.

**Decay/expiry selection (FR-003)**: `provenance = 'synthesized' AND dream_run_id IS NOT NULL AND corroborated = false AND contradicted = false` plus the existing age (`created_at < now() - 30 days`) or `valid_until < now()` condition.

**zm026 re-stamp**: `WHERE provenance = 'synthesized' AND dream_run_id IS NULL` → `provenance = 'prompt_supplied', claim_kind = 'fact'`. It does not change confidence, `reviewed`, `contradicted` or `updated_at`. It reports `restamped` and `decay_damaged` (rows among them with `contradicted AND confidence < 0.25 AND NOT corroborated`).

## Open loop (`open_loops`, ze-worldstate, `zw` chain)

| Field | Change |
|---|---|
| `claim_kind` (column) | Dropped by `zw006`. |
| `OpenLoop.claim_kind` | Read-only property: `loop_claim_kind(state)`. |

**Claim kind by state** (`loop-claim-kind-from-state.md`):

| State | Claim kind |
|---|---|
| suspected | suspicion |
| active, drifting, closed | priority |
| dropped | none |

**Transitions**: `_ALLOWED_TRANSITIONS` is unchanged. A new **resolve** event, available only through `LoopStore.resolve`, moves `suspected | active | drifting → closed`:

```
suspected ──resolve──▶ closed      (new; resolve only)
active    ──resolve──▶ closed      (already legal; now also links evidence)
drifting  ──resolve──▶ closed      (already legal; now also links evidence)
```

On resolve: `closed_at = now()`, `updated_at = now()`, one `memory_relationships` row `(open_loop) -derived_from-> (evidence)` per resolving evidence ref, and no `dismissed_evidence_fingerprint`. It is atomic (one transaction).

## Contact source (`contact_sources`) and contact (`contacts`), ze-personal, `zc` chain

| Field | Change |
|---|---|
| `PersonSource.provenance` | Derived from `source_type`: `manual`, `conversation`, `email`, `calendar` → `prompt_supplied`; `research` → `live_search`; anything else → `ContactSourceTypeError`. Still written to the `provenance` column. |
| `Person.provenance` | Set to the creating source's provenance on every create path (consolidator, graph memory hook, prospecting). |
| `ContactProposal.provenance` | Deleted (it never reached storage). |

**zc041 re-stamp**: `contact_sources.provenance` from `source_type` by the table above (unknown types untouched). Then `contacts.provenance` from the earliest source (`DISTINCT ON (contact_id) ... ORDER BY contact_id, created_at`). Contacts without sources are untouched.

## Hypothesis evidence (`correlation_hypothesis`, ze-correlation; written by ze-personal)

`HypothesisEvidence.origin` from the co-occurrence job: `prompt_supplied` for `email` and `calendar` (was `live_search`). Conversation evidence keeps `synthesized` (outside Clarification Q3). Existing hypothesis rows are not re-stamped (no reader decides behaviour on this origin; R7).

## Licence table (`ze_plugin/contribution.py`)

| Source function | Claim kinds |
|---|---|
| Perception | fact, feedback_record (unchanged) |
| Memory | — (unchanged) |
| **Executive** | **priority, suspicion** (was identity, fact, inference, suspicion, priority) |
| Social cognition | identity (unchanged) |
| Reflection | inference, suspicion (unchanged) |
| Action | action_record (unchanged) |
| Governance | — (unchanged) |
