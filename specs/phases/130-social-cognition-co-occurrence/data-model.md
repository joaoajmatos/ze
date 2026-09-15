# Phase 1 Data Model: Social Cognition Co-Occurrence

## Entities

### Co-occurrence hypothesis (`ze_correlation.types.Hypothesis`, existing type, two new fields)

A `correlation_hypothesis` row. Same dataclass Phase 57/79/111 already use for
every hypothesis in the system; this phase adds no new hypothesis subtype,
just two fields relevant to *this* usage of it.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID` | Existing. |
| `summary` / `narrative` | `str` | Existing. For this phase: `"Alice may work on Launch"` style, generated deterministically from the pair + weighted evidence count, not an LLM call (Decision in research.md — no new LLM surface). |
| `relation` | `Literal["pattern","causal_guess","tension","convergence"]` | Existing closed set. Co-occurrence reuses `"pattern"` — no new relation value is added (FR-009 style discipline: no new taxonomy beyond what's pinned). |
| `confidence` | `float` | Weighted sum/average of evidence via `SOURCE_WEIGHTS`, capped at 1.0. Decays via existing `DecayProfile.TIME_LINEAR` machinery on read, same as every other hypothesis. |
| `evidence` | `list[EvidenceRef]` | One `EvidenceRef` per qualifying communication event (reply thread, meeting, or CC-only mention) inside the 30-day window; `origin` set to the same `Provenance` the evidence's own inflow already carries (`LIVE_SEARCH` for email/calendar, `SYNTHESIZED` for conversation — matching `ze_personal.contacts.types._SOURCE_TYPE_TO_PROVENANCE`, reused as-is rather than re-derived). |
| `entities` | `list[UUID]` | `[person_entity_id, project_entity_id]` for `WORKS_ON`-shaped hypotheses, or `[person_a_id, person_b_id]` for `COLLABORATES_WITH`-shaped ones. |
| `claim_kind` | `ClaimKind` | `INFERENCE` (FR-002) — submitted under `SourceFunction.REFLECTION` (research.md Decision 1). |
| `created_at` | `datetime` | Existing. |
| `surfaced` / `feedback` | existing | Unused by this phase's own logic; untouched. |
| `confirmed` | `bool` **(NEW)** | Default `false`. Set `true` only by an explicit user confirm (mirrors `PersonStore.confirm()`'s boolean-flip pattern). A `true` value alone is sufficient grounds for promotion regardless of the corroboration gate (research.md Decision 3). |
| `promoted_at` | `datetime \| None` **(NEW)** | Set once the corresponding identity edge has been written. Idempotency guard: the job never re-promotes (and never re-submits a seam write for) a hypothesis that already has `promoted_at` set, even if it keeps accumulating fresh evidence afterward. |

**Lifecycle**: `unconfirmed, unpromoted` → (corroboration gate passes, or
`confirmed=true` set) → `promoted` (terminal for this pair; a genuinely new
pattern between the same two entities, e.g. rejoining a project after a long
gap, creates a fresh evidence trail on the *existing* row rather than a second
row — `Hypothesis` is looked up and updated by `(entity_ids)` pair, not
recreated per run).

### Promoted membership (`ze_memory.graph.types.Relationship`, existing type — no schema change)

A `memory_relationships` row with predicate `WORKS_ON` or `COLLABORATES_WITH`,
written only once the hypothesis above is promoted. Identical shape to Phase
128's directly-extracted edges (`confidence: Confidence`, `last_contact:
datetime`) — a reader of the graph cannot distinguish a Phase 128
directly-extracted edge from a Phase 130 promoted-inference edge, by design
(FR-006: "Same kind of edge Phase 128 already extracts"). The only difference
is provenance history, visible only via the originating `Hypothesis` row (kept
around after promotion, not deleted) and the collision log (Phase 126) that
now exists for this write path (research.md Decision 5) but did not for Phase
128's direct path.

### Current membership view (read-time computation, not a stored entity)

"Who is currently on project X" = confirmed `WORKS_ON` edges from `GraphStore`
whose `last_contact` is inside the 30-day window (`ze_proactive.staleness.
is_stale()` returns `False`), computed fresh on every read. No new column, no
new table, no cached list (FR-007). This is exactly Phase 128's existing
`last_contact`-based freshness — Phase 130 introduces no new staleness
mechanism for it, only new *writers* of `WORKS_ON` edges (via promotion) that
this read already covers.

### CoOccurrenceCandidate (`ze_personal.social.types`, NEW — job-internal, never persisted directly)

The job's working representation of one (person, project-or-person) pair
before it becomes a `Hypothesis`. Exists only in memory during a job run.

| Field | Type | Notes |
|---|---|---|
| `source_entity_id` | `UUID` | Person. |
| `target_entity_id` | `UUID` | Project, or another person. |
| `predicate` | `"WORKS_ON" \| "COLLABORATES_WITH"` | |
| `evidence_events` | `list[CoOccurrenceEvidenceEvent]` | Raw evidence gathered this run, before dedup against the existing `Hypothesis.evidence`. |
| `existing_hypothesis_id` | `UUID \| None` | Set when updating a prior row rather than creating one. |
| `existing_edge_exists` | `bool` | `True` when `WORKS_ON`/`COLLABORATES_WITH` already exists for this pair (Edge Case: "if extraction already wrote WORKS_ON, inference MUST NOT duplicate the edge; it MAY reinforce `last_contact`/confidence"). When `True`, the job reinforces the existing edge's `last_contact` directly (same mechanism Phase 128's `upsert_relationship` already provides via its `GREATEST()` clause) and does **not** create or update a hypothesis for this pair — there is nothing left to infer. |

### CoOccurrenceEvidenceEvent (`ze_personal.social.types`, NEW — job-internal)

| Field | Type | Notes |
|---|---|---|
| `source_type` | `"conversation" \| "email" \| "calendar"` | Feeds `SOURCE_WEIGHTS` lookup directly. |
| `is_reply_or_attendee` | `bool` | `True` for a same-thread reply or a calendar attendee; `False` for a CC-only / no-reply mention. Determines conversation-tier vs. research-tier weight (FR-004: "A same-thread reply is conversation-tier; a CC-only / no-reply mention is research-tier"). |
| `event_id` | `str` | Thread id or calendar event id — the "distinct event" unit for Decision 3's corroboration count (not per-message). |
| `occurred_at` | `datetime` | Used for both the 30-day window filter and the "distinct days" corroboration check. |
| `external_ref` | `str \| None` | Carried into `EvidenceRef.external_ref` on promotion to a real `Hypothesis`. |

## Schema Change

Migration `zcor003` on the existing `ze-correlation` (`zcor`) Alembic chain:

```sql
ALTER TABLE correlation_hypothesis
  ADD COLUMN IF NOT EXISTS confirmed BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMPTZ NULL;
```

No index needed — both columns are only read for a specific hypothesis id
(`get()`) or filtered within an already-narrow `list_by_entities()` query
(bounded by the number of known person/project pairs, not a table scan).

## State Transitions

### Hypothesis (this usage only — the type itself has no enforced state machine)

```
(created, confirmed=false, promoted_at=None)
  --(new evidence each job run)--> confidence/evidence updated in place
  --(Decision 3 gate passes OR confirmed set true)--> promotion:
      write WORKS_ON/COLLABORATES_WITH edge via seam (SOCIAL_COGNITION/IDENTITY)
      --> promoted_at = now()
  (promoted_at set) --> job skips this pair for future promotion attempts;
      may still reinforce the now-real edge's last_contact on fresh evidence,
      same as any other confirmed pair (CoOccurrenceCandidate.existing_edge_exists)
```

### Relationship / edge (`memory_relationships`) — unchanged from Phase 128

```
(no row) --(promotion, this phase, OR direct extraction, Phase 128)--> row exists
  --(any fresh evidence, either path)--> last_contact = GREATEST(existing, new)
  --(last_contact ages past 30 days)--> excluded from "currently on this
      project" at read time; row itself is never deleted or marked closed
```
