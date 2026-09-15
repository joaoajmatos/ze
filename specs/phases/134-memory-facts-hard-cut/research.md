# Research: Memory Facts Hard-Cut

## 1. What `"raw"` actually is today

**Decision**: Treat `"raw"` as a missing-epistemic-origin default, not a doctrine category.
Backfill `raw` and NULL → `prompt_supplied`. Keep `'synthesized'` as
`Provenance.SYNTHESIZED`. Fail migration on any other leftover string.

**Rationale**: `zm009` added `provenance TEXT NOT NULL DEFAULT 'raw'`. The primary insert
(`PostgresMemoryStore._write_fact_with_contradiction_check`) **does not write provenance at
all**, so almost every conversation/ingestion fact is `'raw'` regardless of 133's
`Contribution.provenance`. Retrieval then `COALESCE(provenance, 'raw')`. The dialect is an
insert omission plus a default, not an honest stamp.

**Alternatives considered**: Map `raw` → `synthesized` (wrong for onboarding/explicit
proposals). Add `raw` as a fifth `Provenance` member (violates plugin-domain-vocabulary /
doctrine-closed enum). Dual-read old+new (forbidden by Principle VIII).

## 2. Relationship to Phase 133 stamps

**Decision**: After the cut, persist `Contribution.provenance` (already
`SYNTHESIZED` / `PROMPT_SUPPLIED` per 133) onto `Fact` and the INSERT list. Historical rows
use the backfill in §1. Do not re-implement 133's call-site list.

**Rationale**: 133 FR-011 explicitly defers dialect + Protocol deletion here. 133 may still
pass `Fact(provenance="raw")` into the callback if it only stamps the envelope. 134 must
copy envelope provenance onto the domain `Fact` inside the private persist if the dataclass
is still stale — prefer 133 already setting `Fact.provenance` when possible; 134 persist
MUST NOT default to `raw`.

**Alternatives considered**: Wait to persist provenance until a later phase (leaves DEFAULT
`raw`). Infer provenance from `agent` string (lossy).

## 3. How `propose_facts` is removed

**Decision**: Delete `MemoryStore.propose_facts` from
`core/cognition/ze-memory/ze_memory/store.py`. Rename
`PostgresMemoryStore.propose_facts` → `_persist_facts` (or inline into
`_write_fact_with_contradiction_check` loop). Phase 133 `write=` callbacks bind to
`_persist_facts`. No SDK export of the private method. Tests construct
`PostgresMemoryStore` and call `_persist_facts` or the seam — never the Protocol.

**Rationale**: contribution-seam step 6: public ungated API gone when the phase is Done.
Pre-v1 forbids a deprecated alias. 133 allowed the method to remain as callback body.

**Blocker**: If at implement time these still call `propose_facts` as a *front door*
(not as `write=`):

- `ze_core/orchestration/nodes/memory.py`
- `ze_ingestion/sink.py`
- `ze_messenger/inbound/processor.py`
- `ze_onboarding/persistence.py`
- `ze_automation/goals/executor.py`

…stop. Do not wrap. File against 133.

**Alternatives considered**: Keep Protocol method, document "internal only" (still a door).
Rename to `propose_facts_unchecked` (still public).

## 4. INSERT must list provenance (and claim_kind)

**Decision**: `_write_fact_with_contradiction_check` INSERT gains `provenance` (and uses
`fact.claim_kind` when set). `consolidation_store.insert_merged_fact` gains `provenance`
(`SYNTHESIZED` — merge is derived) and keeps `claim_kind='fact'`. Dream promoter already
inserts `provenance='synthesized'` — switch to enum `.value`. Drop column DEFAULT `'raw'`.

**Rationale**: Without INSERT, CHECK + NOT NULL still get `'raw'` from default until we
drop it; 133 stamps would never land on the row.

## 5. SQL that special-cases `'raw'`

**Decision**: Replace `COALESCE(provenance, 'raw')` with `provenance` in:

- `ze_memory/policies.py` (three sites)
- `ze_memory/entity_anchor.py`
- `ze_memory/retrieval_rerank.py`

Update `get_fact_quality` to bucket doctrine values, not `raw` vs `synthesized` only.
Keep `WHERE provenance = 'synthesized'` in promoter, corroboration, zm011-style indexes
(value unchanged). Do not touch `memory_relationships.provenance_id` or dream
`episode_memory.provenance = 'archived'` (different columns).

**Rationale**: `retrieval_provenance` on `Fact` is a retrieval-debug string (`entity_anchor`,
`vector`) — unrelated; leave it.

## 6. `Fact.claim_kind` vs derivation from provenance

**Decision**: Add `claim_kind: ClaimKind` on `Fact` (no silent default that hides bugs —
required on persist). Load from row in `_fact_from_row`. If a writer omits kind, persist
derives using 111's rule with doctrine provenance: `INFERENCE` iff
`provenance is SYNTHESIZED` and not corroborated; else `FACT`. Stop comparing
`fact.provenance == "synthesized"` as a string.

**Rationale**: Column exists (`zm016`); dataclass never grew the field. Confidence stays
`float` on the row (same as `Signal`); decay stays `decay(..., TIME_LINEAR)`.

## 7. REST / UI

**Decision**: `MemoryFactQualityResponse.by_provenance` keys become doctrine strings
(`prompt_supplied`, `synthesized`, and the other two if count > 0). Memory feed item
`provenance: str` still serializes enum `.value`; web badge `=== "synthesized"` keeps
working. No ze-web redesign.

**Alternatives considered**: Keep JSON key `raw` as alias (shim — forbidden).

## 8. Agent context script

**Decision**: Skip. `.specify/scripts` has no update-agent-context helper.

## 9. Latest migration

**Decision**: `zm020_facts_doctrine_provenance.py`, `down_revision = "zm019"`. If 133 or
another in-flight memory migration lands `zm020` first, take the next free `zm` id; do not
fork the chain.
