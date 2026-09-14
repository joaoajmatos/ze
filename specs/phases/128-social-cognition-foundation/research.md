# Phase 0 Research: Social Cognition Foundation

Grounding facts were gathered by reading the current implementations of every
surface this phase touches (`core/ze-memory`, `plugins/ze-personal`,
`core/ze-priority`, `core/ze-agents/ze_agents/claims.py`). Findings below are
verified against code, not assumed.

## 1. `entity_type` and predicate vocabularies are enforced differently today

**Decision**: Add `"project"` as a Python-level documented value only —
mirror the existing pattern exactly, do not introduce an enum.

**Rationale**: `entity_type` (`core/ze-memory/ze_memory/types.py:15,65`) is a
bare `str` field with a `# "person" | "org" | ...` comment; there is no
`ALL_ENTITY_TYPES` frozenset and no DB `CHECK` constraint
(`zm001_memory_tables.py` — `entity_type TEXT NOT NULL`, unconstrained).
Predicates, by contrast, *are* a real `frozenset[str]`
(`core/ze-memory/ze_memory/graph/predicates.py:28-38`,
`ALL_PREDICATES`), though still unenforced at the DB or `upsert_relationship`
write path — it's a documentation/lint-level vocabulary. FR-001/FR-002 match
these two existing conventions exactly: extend the `entity_type` comment,
add `WORKS_ON`/`COLLABORATES_WITH` as new module-level constants folded into
`ALL_PREDICATES`, each with the same one-line semantic comment style as
`PARTICIPATES_IN`.

**Alternatives considered**: Introducing an `EntityType` enum for
`entity_type` was rejected — out of scope (this phase adds one value to an
existing convention, it does not redesign the convention), and Constitution
III reserves core-owned closed enums for values a governing doctrine
mandates as an exact closed set; `entity_type` is not currently one of
those.

**Extractor gap found (must fix for FR-003 to work end-to-end)**:
`core/ze-memory/ze_memory/extractor.py:267-279` — the LLM extraction prompt
lists `"person|organisation|pl..."` (note: `"organisation"`, not `"org"` —
a pre-existing mismatch versus the `types.py` comment) and defaults any
entity type the LLM doesn't recognize to `"concept"`. Without adding
`"project"` to this prompt/mapping, the generic extractor would silently
misclassify project mentions as `"concept"`. This phase must update the
extractor's allowed-type list to include `"project"` — otherwise FR-003
("extract `project` entities... using the same... pattern already used for
`person`") is unreachable through the generic extraction path. (The
pre-existing `"organisation"`/`"org"` mismatch is not this phase's bug to
fix and is left alone.)

## 2. `Relationship.confidence` retrofit: read-time decay, not a batch job

**Decision**: `Relationship.confidence` (currently a plain `float` at
`core/ze-memory/ze_memory/graph/types.py:25`) becomes a
`ze_agents.claims.Confidence`-typed field, **computed at read time** in
`GraphStore`'s row-hydration path:
`Confidence(value=decay(row["confidence"], DecayProfile.TIME_LINEAR, elapsed_days=(now - row["last_contact"]).days), decay_profile=DecayProfile.TIME_LINEAR)`.
The DB `confidence` column keeps storing the undecayed, reinforced base
value (bumped via the existing `GREATEST(...)` `ON CONFLICT` clause in
`upsert_relationship`, `core/ze-memory/ze_memory/graph/store.py:56-58`); a
new `last_contact TIMESTAMPTZ` column drives the elapsed-time calculation.

**Rationale**: Two decay-application patterns already exist in the
codebase, and neither fits SC-004's requirement ("confidence, read at any
point ..., reflects real elapsed-time decay"):
- `HypothesisDecayJob` (`core/ze-correlation/.../jobs/hypothesis_decay.py`)
  and `cascade_from_evidence()`
  (`core/ze-worldstate/ze_worldstate/decay.py`) both **write** a decayed
  value back to storage — via a scheduled sweep or an event-triggered
  cascade, respectively. Reusing this for `Relationship` would require a
  new scheduled job with its own cadence, which the spec's own
  "reconciliation, not new-build" framing and FR-006 (no new
  relationship-specific mechanism) argue against.
- `ze_priority.scoring.score_loop/score_goal/score_hypothesis`
  (`core/ze-priority/ze_priority/scoring.py:34-100`) construct a
  `Confidence` value fresh on every call and, for `score_goal`, literally
  call `decay()` against elapsed idle-days at scoring time — this is the
  closest existing precedent for "value that reflects elapsed time whenever
  it's read," and is the pattern this phase generalizes to
  `Relationship.confidence`.

Because `GraphStore.upsert_relationship`'s `ON CONFLICT` `DO UPDATE SET
confidence = GREATEST(...)` already exists as the reinforcement path (US1
acceptance scenario 3: "confidence is reinforced... not duplicated"), this
decision reuses that clause unchanged and adds `last_contact = the
newer of the two values` to the same `DO UPDATE`.

**Alternatives considered**: A scheduled `RelationshipDecayJob` mirroring
`HypothesisDecayJob` was rejected — FR-006 explicitly forbids a new
relationship-specific mechanism, and a batch job introduces a staleness
window (decay only reflected after the next sweep) that read-time
computation avoids for free using the same `decay()` function.

**Migration**: `core/ze-memory` `zm` chain, next revision `zm019` (chain
head confirmed at `zm018_signal_provenance.py`). Adds `last_contact
TIMESTAMPTZ` to `memory_relationships`, backfilled to `created_at` for
existing rows (matches the spec's edge case: "if no activity has ever
occurred beyond creation, `last_contact` reflects the edge's
creation-triggering event, not a null"). No column type change to
`confidence` — it stays a raw `FLOAT` in storage; only the Python
dataclass field type changes.

## 3. `PriorityView`'s fourth source must not create a core→plugin dependency

**Decision**: Define a structural `Protocol` in `core/ze-priority`
(e.g. `RelationshipStalenessSource`, matching
`PersonStore.list_stale_for_follow_up(stale_days, limit) ->
list[StaleFollowUpNudge]`'s existing shape) that `PriorityView` depends on
as an *optional* fourth constructor argument. `ze-personal`'s `PersonStore`
satisfies it structurally with no code changes on the plugin side (Python
structural typing — no import required in either direction at runtime); the
composition root (`apps/ze-api/ze_api/container.py`) supplies the concrete
`PersonStore` instance when constructing `PriorityView`.

**Rationale**: `PriorityView.__init__` today
(`core/ze-priority/ze_priority/view.py:40-48`) takes `LoopStore`,
`GoalStore`, `PostgresHypothesisStore` — all three are `core/`-owned,
domain-free types (loops/goals/hypotheses are generic constructs owned by
other core packages). "Stale relationship" is inherently `ze-personal`
(contacts) domain. Constitution III is explicit: `core/` packages carry no
domain knowledge, and the dependency direction is absolute — `ze-priority`
importing `PersonStore` from `plugins/ze-personal` would invert it. This
codebase has already solved exactly this shape of problem once: Phase 60's
`SignalSource` protocol (`ze-plugin`) lets domain plugins contribute signals
to core engine code without the core package importing plugin types. This
phase reuses that precedent's shape (protocol in core, concrete
implementation in the plugin, wired at the `apps/` composition root) rather
than inventing a new cross-layer pattern.

**Alternatives considered**: Importing `PersonStore` directly into
`ze-priority` was rejected outright — direct constitutional violation.
Making `ze-priority` depend on `ze_sdk.*` (as plugins do) was also
rejected — `ze-priority` is a `core/` package and per the dependency graph
in `CLAUDE.md`, only `apps/` and `plugins/` depend on `ze_sdk`; core
packages depend on other core packages directly, never through the SDK
re-export layer.

`PriorityView.rank()`'s existing `SourceKind` (`Literal["loop", "goal",
"hypothesis"]`, `core/ze-priority/ze_priority/types.py:13`) gains a fourth
member, `"relationship"`; a new `RelationshipSignal` dataclass and
`score_relationship_staleness()` function follow the exact shape of the
three existing `score_*` functions in `scoring.py`. The existing
try/except-per-source + `failed: set[SourceKind]` degradation loop in
`rank()` (FR-009's existing behavior, `view.py:50-94`) gets a fourth
try/except block, consistent with FR-010's requirement that partial failure
still ranks the sources that succeeded — the "all sources failed" hard-fail
condition (`if len(failed) == 3`) becomes `if len(failed) == len(sources)`
(4, once the relationship source is present) rather than a hardcoded `3`.
When the optional fourth source isn't supplied (e.g. in existing tests that
construct `PriorityView` with only three stores), the relationship source
is simply skipped, not counted as failed — preserving every existing
`PriorityView` test's behavior unchanged.

## 4. Extending the extraction pipeline to projects and relationship edges

**Decision**: Extend `ContactsConsolidator._extract_candidates()`
(`plugins/ze-personal/ze_personal/contacts/consolidator.py:127-158`) — the
existing LLM-based conversation-episode extraction that already produces
`ContactProposal` — to also emit project mentions and
`WORKS_ON`/`COLLABORATES_WITH` edge mentions in the same LLM call, as new
`ProjectProposal`/`RelationshipEdgeProposal`-shaped output. Route both
through the existing `memory_hooks.py` result-hook path
(`plugins/ze-personal/ze_personal/graph/memory_hooks.py:21-60`) alongside
`contact_proposal_hook`, writing directly via `GraphStore.upsert_entity`
(new `entity_type="project"`) and `GraphStore.upsert_relationship`
(`predicate="WORKS_ON"`/`"COLLABORATES_WITH"`) — **not** through
`PersonStore.add_relationship()`, which this phase retires. Email
(`extract_email_contacts`) and calendar (`extract_calendar_contacts`)
extractors in `extractors.py` are extended the same way, since both already
produce per-thread/per-event structured output that can carry a project
mention or a co-attendee collaboration signal.

**Rationale**: FR-003 requires "the same... extraction call sites and
upsert pattern already used for `person` entities... no new, separate
extraction pipeline." `ContactsConsolidator` and the two extractor
functions are the complete set of existing call sites that produce
person-shaped proposals from conversation/email/calendar; extending their
existing LLM prompts/output schemas (rather than adding a second, parallel
extraction pass) is the literal reading of FR-003.

**Alternatives considered**: A dedicated `ProjectExtractor` running as a
separate pass over the same inputs was rejected — FR-003 explicitly rules
out "a new, separate extraction pipeline," and a second LLM pass over the
same conversation/email/calendar data doubles extraction cost for no
architectural benefit given the existing consolidator already parses this
content once per episode.

## 5. `contact_relationships` retirement is a clean drop, no backfill

**Decision**: New `plugins/ze-personal` migration, `zc` chain, next
revision `zc029` (chain head confirmed at `zc028_contacts_claim_kind.py`).
`DROP TABLE contact_relationships` (dropping the `claim_kind`/`provenance`
columns `zc028` added along with it — no separate `ALTER` needed since the
whole table goes). Delete `PersonRelationship`
(`ze_personal/contacts/types.py:58-68`), `PersonStore.add_relationship()`
and `.get_relationships()` (`store.py:329-386`), the
`_domain("contacts.relationships", "contact_relationships", 20)`
registration in `plugin.py:182`, the `contact_relationships` truncation
entry in `core/ze-onboarding/ze_onboarding/reset.py:26`, and every
reference in `plugins/ze-personal/tests/contacts/test_person_store.py` and
`test_types.py`.

**Rationale**: Confirmed by repo-wide grep — zero production callers of
`add_relationship`/`get_relationships` beyond the two test files; the
table's own creation migration (`zc005_contacts_and_channels.py`) carries
no seed data. This is a straight retirement per the spec's own resolved
clarification, not a migration with a backfill step.

## 6. Morning briefing call-site swap

**Decision**: `MorningBriefing` (`plugins/ze-personal/ze_personal/jobs/
briefing.py`, `@proactive_job`, `job_id="morning_briefing"`) gains a
`priority_view: PriorityView` constructor dependency alongside its existing
`person_store: PersonStore`. The call at `briefing.py:78-80`
(`self._persons.list_stale_for_follow_up(self._stale_days,
self._max_nudges)`) is replaced with a read of `PriorityView.rank()`'s
output filtered to `source_kind == "relationship"`, consistent with FR-009.
The `stale_days`/`max_nudges` config keys (`briefing.py:49-51`) are left in
`config.yaml` schema-wise but stop governing the nudge directly, per the
spec's own resolved clarification (Session 2026-08-26, Q3) — this is a
deliberate behavior change, not a compatibility shim to preserve.

## Summary of migration/revision facts

| Chain | Owning package | Current head | This phase's revision |
|---|---|---|---|
| `zm` | `core/ze-memory` | `zm018` | `zm019` — adds `last_contact` to `memory_relationships` |
| `zc` | `plugins/ze-personal` | `zc028` | `zc029` — drops `contact_relationships` |

No other package's migration chain is touched.
