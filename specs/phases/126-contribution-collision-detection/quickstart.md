# Quickstart: Validating Contribution Collision Detection

## Prerequisites

```bash
make db-up
make migrate            # picks up the new zcol001 migration via the meta-runner
make dev                # apps/ze-api on :8000
```

## Scenario 1 — a real collision gets logged (User Story 1)

1. Submit a `FACT` contribution from `perception` linking entity X with content "X moved to
   Berlin" through its normal producer path (e.g. a `Signal` ingested with `entities=[X]`,
   `title`/`summary` set accordingly).
2. Within the recency window, submit an `INFERENCE` contribution from `reflection` linking the
   same entity X with content implying X is still in its prior location (e.g. via the
   correlation engine's hypothesis path).
3. `GET /api/v0/collisions?entity_id=<X>` and confirm one entry referencing both contributions'
   `domain_id`/`producer_kind`/`source_function`/`claim_kind`, with a non-empty
   `conflict_summary`.
4. Confirm both original writes succeeded through their normal read paths (the `Signal` is
   queryable, the `Hypothesis` is queryable) — collision logging must not have blocked either.

**Expected outcome**: exactly one `CollisionLogEntry`, both source writes intact — matches
SC-001.

## Scenario 2 — thematic overlap without conflict is not logged (User Story 2)

1. Submit two contributions from different `source_function`s linking the same entity with
   compatible (non-conflicting) content.
2. `GET /api/v0/collisions?entity_id=<that entity>` and confirm zero entries.

**Expected outcome**: no `CollisionLogEntry` created — matches SC-002.

## Scenario 3 — query surface filters correctly (User Story 3)

1. Seed several collisions across different `source_function` pairs and entities (repeat
   Scenario 1's shape with different entities/functions).
2. `GET /api/v0/collisions?entity_id=<one specific entity>` — confirm only matching entries
   return.
3. `GET /api/v0/collisions?source_function=reflection` — confirm only entries where `reflection`
   appears on either side return.
4. `GET /api/v0/collisions?since=<timestamp>` — confirm date-range filtering works.

**Expected outcome**: filtered result sets match FR-009's filter set exactly.

## Fault-injection check (SC-003)

1. Point the injected `NLIClient` mock at a version whose `scores()` raises or returns `None` for
   every pair.
2. Repeat Scenario 1's writes.
3. Confirm both writes still succeed, no collision is logged (fail-open, FR-008), and no
   exception escapes the write path.

## Non-interference check (FR-007, User Story 1 Acceptance Scenario 2)

1. Submit two conflicting `FACT` contributions from the *same* `source_function` (e.g. two
   memory-originated facts that `ze-memory`'s own NLI-based fact-contradiction path already
   resolves).
2. Confirm zero `CollisionLogEntry` rows are created for this pair — it never became a candidate
   pair in the first place (different-`source_function` filter in FR-002).

## Running the test suite

```bash
make test-collision     # new package's unit tests (mocked NLIClient, mocked asyncpg)
make test-worldstate    # existing extraction.py tests must still pass unchanged
make test-memory        # existing retriever.py / dream_pass.py tests must still pass unchanged
make test-correlation   # existing engine.py tests must still pass unchanged
make test-personal      # existing consolidator.py / memory_hooks.py tests must still pass unchanged
```
