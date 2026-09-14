# Quickstart: validating Social Cognition Foundation

Prerequisites: `make db-up && make migrate` (picks up `zm019` and `zc029`),
`make dev` running.

## User Story 1 — people and projects in one connected graph

1. Send a message through the chat client that mentions working on a named
   project with another person (e.g. "I'm working on the Q3 launch with
   Maria"), or trigger the existing contact-consolidation job over a fixture
   conversation containing that content.
2. Open `/brain/graph` (or call `GraphStore.expand()` directly) starting
   from the `person` entity for "Maria" — confirm a `WORKS_ON` edge to a
   `project` entity named "Q3 launch" is reachable, with `confidence` and
   `provenance` populated (data-model.md §2, contracts/memory-graph-
   vocabulary.md).
3. Repeat the same mention in a later conversation turn. Confirm via
   `GraphStore.list_relationships()` (or the graph view) that there is
   still exactly one `WORKS_ON` edge between the two entities — not two —
   and that its `confidence` value increased (reinforcement, not
   duplication; data-model.md §3).
4. Send a message mentioning two people working together with no project
   named. Confirm a `COLLABORATES_WITH` edge appears directly between their
   two `person` entities.

## User Story 2 — relationship state is honest about staleness

1. Create (or reuse) a `WORKS_ON`/`COLLABORATES_WITH` edge from Story 1.
   Read its `confidence` immediately — record the value.
2. In a test (not production — no real clock manipulation needed in prod),
   construct a `Relationship` with `last_contact` set 60+ days in the past
   and confirm `relationship.confidence.value` is lower than the stored
   base, computed via `ze_agents.claims.decay(..., DecayProfile.TIME_LINEAR,
   elapsed_days=...)` — this is `core/ze-memory`'s
   `tests/graph/test_store.py` (or equivalent) exercising the read-time
   decay path from data-model.md §4.
3. Send a new message referencing the same relationship. Confirm
   `last_contact` advances to the new mention's timestamp and `confidence`
   is no longer decayed relative to "now."

## User Story 3 — stale-relationship nudges compete fairly

1. Seed one stale relationship (via `PersonStore.list_stale_for_follow_up`
   returning a non-empty result) and one eligible open loop, on the same
   day, with the shared daily attention budget set to admit only one item
   (existing `core/ze-priority` test fixtures already do this for
   loop-vs-goal-vs-hypothesis; extend the same fixture pattern with a
   relationship item).
2. Call `PriorityView.rank()` with all four sources wired (per
   contracts/priority-relationship-source.md). Confirm the returned
   ranking's top item is whichever of the two `PriorityView` actually
   scores higher — and that this can be the relationship item, not always
   the loop (proves the relationship source competes on equal footing, not
   as a hardcoded fallback).
3. Run (or unit-test) `MorningBriefing.run()` with the same fixtures and
   confirm its relationship-staleness line comes from `PriorityView`'s
   ranked output, not a direct `person_store.list_stale_for_follow_up(
   stale_days, max_nudges)` call (grep the diff — that call site should no
   longer exist in `briefing.py`).
4. Make the relationship source raise (simulate a `PersonStore` failure).
   Confirm `PriorityView.rank()` still returns ranked loop/goal/hypothesis
   items — degradation, not a hard failure (FR-010).

## Regression check — retired `contact_relationships`

1. `make migrate` should apply `zc029` cleanly against a DB that has never
   had rows in `contact_relationships` (true for every real deployment per
   research.md §5).
2. `grep -rn "PersonRelationship\|contact_relationships\|add_relationship\|get_relationships" plugins/ze-personal/` (excluding this phase's own new code) should return nothing.
3. `make test-personal` and `make test-onboarding` still pass with no test
   referencing the deleted table/type/methods.
