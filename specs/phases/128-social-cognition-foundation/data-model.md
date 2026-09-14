# Phase 1 Data Model: Social Cognition Foundation

All entities below live in `core/ze-memory`'s existing graph (`memory_entities` /
`memory_relationships`); this phase adds no new store or table for domain state
(see `research.md` §1-2). One plugin-owned table is removed (§5).

## 1. `project` — new `entity_type` value

Not a new dataclass — an additional value flowing through the existing
`Entity` dataclass (`core/ze-memory/ze_memory/types.py`):

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID \| None` | unchanged |
| `entity_type` | `str` | gains `"project"` as a documented allowed value, alongside `person \| org \| topic \| ticker \| place \| product` |
| `canonical_name` | `str` | the project's name/identifier, extracted the same way a person's name is |
| `aliases` | `list[str]` | unchanged |
| `attrs` | `dict` | whatever the generic extraction path already captures — no project-specific attribute schema is introduced |

**Validation**: none beyond what `entity_type` already gets today (no DB
`CHECK`, no Python enum) — see research.md §1 for why this matches the
existing convention rather than introducing one.

**Extraction path**: `core/ze-memory/ze_memory/extractor.py`'s generic
LLM-extraction prompt gains `"project"` to its recognized-type list (today
defaults unrecognized types to `"concept"` — see research.md §1); the
`plugins/ze-personal` conversation/email/calendar extraction call sites
(research.md §4) additionally emit project mentions in
`ProjectProposal`-shaped output, written via `GraphStore.upsert_entity`
mirroring `PersonStore._write_entity()`.

## 2. `WORKS_ON` — new predicate

A `Relationship` row (see §3 for the retrofitted type) with:

| Field | Value |
|---|---|
| `predicate` | `"WORKS_ON"` |
| `source_type` | `"person"` |
| `target_type` | `"project"` |
| `confidence` | `Confidence` (see §3) |
| `last_contact` | set from the extraction event's timestamp |

Added to `core/ze-memory/ze_memory/graph/predicates.py`'s `ALL_PREDICATES`
with the comment `# person → project`.

## 3. `COLLABORATES_WITH` — new predicate

Same `Relationship` shape as `WORKS_ON`, but:

| Field | Value |
|---|---|
| `predicate` | `"COLLABORATES_WITH"` |
| `source_type` | `"person"` |
| `target_type` | `"person"` |

Added to `ALL_PREDICATES` with the comment `# person ↔ person`. Per FR-012,
this is the only person↔person predicate this phase introduces —
`Person.classification` (`personal \| professional \| unknown`, already
existing) remains the mechanism for distinguishing relationship domains.

**Reinforcement, not duplication** (US1 acceptance scenario 3): both edge
kinds go through `GraphStore.upsert_relationship`'s existing `ON CONFLICT
(source_id, predicate, target_id) DO UPDATE SET confidence =
GREATEST(existing, incoming)` clause, extended to also advance
`last_contact` to the newer of the two timestamps on conflict.

## 4. `Relationship` — retrofitted `confidence`, new `last_contact`

`core/ze-memory/ze_memory/graph/types.py`:

| Field | Before | After |
|---|---|---|
| `confidence` | `float = 1.0` | `Confidence` (from `ze_agents.claims`), constructed at read time as `Confidence(value=decay(stored_float, DecayProfile.TIME_LINEAR, elapsed_days=(now - last_contact).days), decay_profile=DecayProfile.TIME_LINEAR)` |
| *(new)* `last_contact` | — | `datetime`, set only from processed communication-graph activity (never user/tool-settable — FR-005) |

**Storage**: `memory_relationships.confidence` stays a raw `FLOAT` column —
it holds the undecayed, reinforced base value. `last_contact
TIMESTAMPTZ` is a new column (migration `zm019`), backfilled to
`created_at` for pre-existing rows. The decay computation happens in
`GraphStore`'s row → `Relationship` hydration, not in SQL and not in a
scheduled job — see research.md §2 for why.

**State transitions**: none beyond "created" → "reinforced" (on repeat
mention, via the `ON CONFLICT` path above). No explicit lifecycle state is
added to `Relationship` itself.

## 5. Retired: `PersonRelationship` / `contact_relationships`

Deleted entirely, no replacement data shape (the same information now
lives as `COLLABORATES_WITH` edges in `memory_relationships`, per §3):

- Type: `plugins/ze-personal/ze_personal/contacts/types.py`'s
  `PersonRelationship` dataclass.
- Table: `contact_relationships` (created `zc005`, altered `zc028`) —
  dropped by `zc029`, no backfill (research.md §5).
- Methods: `PersonStore.add_relationship()`, `PersonStore.get_relationships()`.
- Registration: `plugin.py`'s `_domain("contacts.relationships",
  "contact_relationships", 20)` contribution-domain entry.
- Reset hook: `core/ze-onboarding/ze_onboarding/reset.py`'s truncation
  entry for the table.

## 6. `PriorityView`'s fourth ranked source

Not a persisted entity — a read-time signal, computed the same way the
existing three sources are (`core/ze-priority/ze_priority/scoring.py`):

| Type | Shape |
|---|---|
| `RelationshipStalenessSource` (Protocol, new, in `core/ze-priority`) | Structurally matches `PersonStore.list_stale_for_follow_up(stale_days, limit) -> list[StaleFollowUpNudge]` — no plugin import in `ze-priority` (research.md §3) |
| `RelationshipSignal` (dataclass, new, in `ze_priority/types.py`) | `name: str`, `days_ago: int` — mirrors `StaleFollowUpNudge`'s two fields |
| `SourceKind` (existing `Literal`) | Gains `"relationship"` as a fourth member |
| `score_relationship_staleness()` (function, new, in `scoring.py`) | Same signature shape as `score_loop`/`score_goal`/`score_hypothesis`: takes one `StaleFollowUpNudge`-like item, returns a `PriorityItem` with `source_kind="relationship"` |

`PriorityView.__init__` gains an optional fourth constructor argument
(`relationship_source: RelationshipStalenessSource | None = None`) so every
existing test that constructs `PriorityView` with three stores keeps
working unchanged; `rank()` gains a fourth try/except block following the
existing per-source degradation pattern (FR-009/FR-010), and the
all-sources-failed hard-fail check becomes relative to however many sources
were actually supplied rather than a hardcoded `3`.

`apps/ze-api/ze_api/container.py` wires the concrete `PersonStore` instance
into `PriorityView`'s new constructor argument at composition-root time.

## 7. Morning briefing's relationship-staleness read

`plugins/ze-personal/ze_personal/jobs/briefing.py`'s `MorningBriefing`
gains a `priority_view: PriorityView` constructor dependency. No new type —
it filters `PriorityView.rank()`'s `PriorityRanking.items` to
`source_kind == "relationship"` in place of its old direct
`person_store.list_stale_for_follow_up(stale_days, max_nudges)` call
(research.md §6).
