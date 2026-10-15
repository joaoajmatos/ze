# Feature Specification: Executive Repair

**Feature Branch**: `170-executive-repair`

**Created**: 2026-10-12

**Status**: Implemented

**Input**: User description: "Phase 1a of the executive-function direction (`specs/arch/executive-function.md`, decisions D1 to D7). Repair the executive layer so it acts: loops drift after their window (F1), stuck goals are found and ranked (F3), loops carry evidence and the push grounding gate means something (F9), the priority snapshot reports failed sources and no longer 500s on relationship items (F13), dead code and unread config go (§3.2), and a real-Postgres test harness stops the mock-store defect class from recurring."

**Governed by**: [`specs/arch/executive-function.md`](../../arch/executive-function.md) (findings F1, F3, F9, F13 and §3.2), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/attention-arbitration.md`](../../arch/attention-arbitration.md), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md). Phases [109](../109-open-loop-substrate/spec.md), [110](../110-open-loop-drift-surfacing/spec.md), [123](../123-attention-arbitration/spec.md), [127](../127-priority-override/spec.md), [132](../132-priority-turn-surfacing/spec.md), [168](../168-loop-extraction-gate/spec.md), [169](../169-loop-track-tool/spec.md).

**Depends on**: Phase 168 Implemented (loop gate, `LoopInflow`). Phase 169 spec pinned (its `stamp_declared` and `drifting → active` revive); 170 implementation starts after 169 lands on `main`, and its first task re-reads the 169 diff (see Assumptions).

**Does not change**: priority scoring and ranking order (F6, Phase 175), the confirmation UX for suspected loops (F2, Phase 171), corroboration promotion (Phase 172), commitment intake and double-booking (F4, Phase 173), push budget scope, quiet hours and tiers (F5, Phase 177), the English-only "what's open" trigger (F10, Phase 171), the `open_loops` table shape (no migration), `OpenLoop.goal_id` (kept for Phase 173), the loop gate questions, bars or calibration, the contribution seam and claim vocabulary.

---

## Overview

The executive-function audit found that the layer is built broadly and acts narrowly. Four defects sit on the path from "the user said they would do something" to "Ze notices it went quiet", and each was reproduced against real code, not a mock:

- **F1.** The absence-drift sweep selects loops with `updated_at <= confirmed_at`. Every write that sets a drift deadline also bumps `updated_at`, so the predicate is false for every loop made through the real store (scratch Postgres: `updated_at` was 1.4 ms and 7.8 ms after `confirmed_at`). No loop ever drifts by absence.
- **F3.** `PostgresGoalStore.list_stuck` joins every gate that is `pending` or `awaiting_approval`. Gates that have not fired have `fired_at` NULL, and the code calls `fired_at.tzinfo`. Any goal that is awaiting a gate and has a later unfired gate raises `AttributeError`. On the dev database one goal sat 108 days at a gate with no alert, and `PriorityView.rank()` silently dropped every goal.
- **F9.** `LoopInflow` creates every loop with `evidence_refs=[]`. The contradiction cascade cannot reach them, the push grounding gate passes vacuously, and every dropped loop gets the same evidence fingerprint, so a dropped topic never comes back.
- **F13.** `GET /api/v0/priority/snapshot` declares `source_kind` as `Literal["loop","goal","hypothesis"]`, but `PriorityView` also ranks `relationship` items once the person store is wired (it is, in `container.py`). The response fails validation whenever a stale-relationship nudge exists.

The same reading found config and code that nothing uses, and a pattern behind F1, F3 and the 168 finding: unit tests mock the store, so SQL predicates and joins are never run against a row. This phase repairs the four defects, removes the dead pieces, makes the failed-source degradation visible instead of a log line, and adds a real-Postgres test harness that is opt-in (no Docker for `make test-py`).

## Clarifications

### Session 2026-10-12

- Q: How does F1 get fixed: a new `last_activity_at` column, or no new column? → A: **(user accepted, 2026-10-12)** **No new column and no migration.** The earlier note proposed `last_activity_at` (migration `zw003`). Reading the code again, the bug is the coupling of drift to `updated_at`; a column is not needed once the drift test is "deadline passed". Corroboration is expressed by moving the deadline: a new store method `record_corroboration` pushes `drift_deadline` to `GREATEST(current, now() + default window)` on an `active` loop. The sweep selects `state = 'active' AND drift_deadline <= now()`. This also removes the old flaw where one early touch exempted a loop from drift forever. Alternative kept in `research.md` R1 (add the column) if the user prefers it.
- Q: What does Phase 169's revive do to this? → A: Nothing breaks. 169 pins `stamp_declared` (state `active`, confidence 0.9, `confirmed_at = now`, `drift_deadline = now + window`, `drift_rationale` NULL, `updated_at = now`, all from one `now()`). The new predicate ignores `confirmed_at` and `updated_at`, so a revived loop is a drift candidate again exactly when its new deadline passes. A Postgres test covers drift → revive → drift.
- Q: Which evidence does each inflow attach (F9)? → A: conversation: the episode written for that turn; email: the episode the processor writes for the message; ingestion: the `ingestion` ref (its id is already a UUID); calendar: none (no record with a UUID exists; recorded as a known gap, Phase 173 can revisit). `write_episode` returns the new episode id.
- Q: Does evidence on a loop make the push grounding gate real, and is that safe? → A: It would make it real, and unsafe as written: the gate checks the *drift rationale* ("no corroborating evidence since…") against the evidence text, and an absence statement is not entailed by what the user said. With evidence present the check would fail for every loop and block all loop pushes. The gate now checks the loop **title** against the evidence text (is this loop grounded in what the user said). Novelty still uses the rationale.
- Q: What are the fingerprint semantics for dropped loops? → A: Unchanged mechanism, now meaningful. The fingerprint is a hash of the dropped loop's evidence set. A later inferred loop that matches a dropped loop is suppressed only when its evidence set equals the dropped one (the same evidence). A new message is new evidence and may re-suspect the topic; it then starts `suspected` and is bounded by the 14-day expiry and the confirmation path. A loop with no evidence (calendar) matching a dropped evidence-less loop is suppressed, as today. **(user accepted, 2026-10-12):** re-suspect a dropped topic on new evidence.
- Q: Does the declared path dedup? → A: Today it does not (two "I need to renew my passport" turns make two active loops). It now calls `find_matching_loop` over open states first. On a match it links the new evidence and calls `record_corroboration`; it does not change the matched loop's state (promoting a suspected match belongs to 169's tracker and Phase 172).
- Q: How does the real-Postgres harness run without making `make test-py` need Docker? → A: Tests live in `apps/ze-api/tests/pg/`, carry `@pytest.mark.pg`, and are skipped unless `ZE_TEST_PG=1`. `make test-pg` sets it and the harness starts a throwaway `pgvector/pgvector:pg16` container (or uses `ZE_TEST_PG_URL`), runs the real migrations through `ze_api.migrate`, and removes the container. Default `make test`, `test-py` and `test-all` collect and skip these tests with a reason. Details: `research.md` R2.
- Q: What does the priority snapshot REST change look like? → A: `GET /api/v0/priority/snapshot` returns `{ "items": [...], "sources_failed": [...] }` instead of a bare list (a hard cut; one web consumer). `source_kind` accepts `relationship` everywhere it appears. The web page shows a notice naming unavailable sources.
- Q: What about `worldstate.push.*` config? → A: Wire it. `worldstate.push.enabled`, `thresholds` and `inline_cooldown_hours` are passed to the loop candidate path by `compose.py`. `worldstate.drift.window_days` is deleted from the config (the default window is a code constant and is not configurable today).
- Q: What does honoring `correlation.push.enabled` and `dry_run` mean? → A: **(user accepted, 2026-10-12)** `enabled: false` yields no hypothesis candidates for arbitration. `enabled: true, dry_run: true` logs `correlation_push_dry_run` with the would-be push and yields none. Only `enabled: true, dry_run: false` sends. **User-visible effect:** the shipped config is `enabled: false`, so hypothesis pushes (which today can fire despite the flag) stop until the user turns them on.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A quiet loop drifts and can be surfaced (Priority: P1)

The user said "I need to renew my passport before the March trip". Ze created an active loop with a drift window. Nothing about it happened for the whole window. Today the loop stays `active` forever. After this phase the daily sweep moves it to `drifting` with a hedged rationale, and from then on the push candidate path, the ranking bonus and the "still open" mention see it.

**Why this priority**: Without this, Phase 110's "your loop went quiet" never happens and the push half of the shared attention budget has no loop candidates.

**Independent Test**: In the Postgres harness, create a loop through the real store with a 1-day window, move its deadline into the past, run `DriftSweepJob`, and assert the loop is `drifting` with a rationale. Run the same with a loop that was corroborated after confirmation and assert the deadline moved and the loop did not drift.

**Acceptance Scenarios**:

1. **Given** an `active` loop whose `drift_deadline` has passed, **When** the sweep runs, **Then** the loop becomes `drifting` and gets an absence rationale.
2. **Given** an `active` loop whose deadline is in the future, **When** the sweep runs, **Then** nothing changes.
3. **Given** an `active` loop that received corroboration (a new evidence ref on a re-extraction) after confirmation, **When** its original deadline passes, **Then** the deadline had been moved to at least now plus the default window and the loop does not drift yet.
4. **Given** a loop revived by Phase 169 (`stamp_declared`), **When** its new deadline passes, **Then** it drifts again.
5. **Given** a `suspected`, `closed`, `dropped` or `drifting` loop, **When** the sweep runs, **Then** it is not selected.
6. **Given** a drifting loop that passes the push bar, **When** `LoopSurfacer.eligible_candidates` runs, **Then** it is returned (acceptance run).

---

### User Story 2 - A goal stuck at a gate is found, alerted and ranked (Priority: P1)

The user has a multi-week goal paused at a verification gate, with later gates not yet fired. Today the stuck-goal query throws, the weekly alert never goes out, and the priority page shows no goals at all. After this phase the goal appears once, with the days it has waited at its first open gate.

**Why this priority**: Stuck-goal detection and goal ranking are the "you are not following through" signal for the heaviest commitments, and a normal multi-gate goal breaks both.

**Independent Test**: In the harness, create a goal with one fired `awaiting_approval` gate (10 days ago), three unfired `pending` gates and one approved gate. `list_stuck(7, 14)` returns exactly one `awaiting_gate` entry with 10 idle days; `PriorityView.rank()` reports no failed source and includes the goal.

**Acceptance Scenarios**:

1. **Given** a goal in `awaiting_gate` with unfired `pending` gates after the open one, **When** `list_stuck` runs, **Then** it returns one entry for the goal, built from the earliest fired open gate, and does not raise.
2. **Given** a goal with two fired open gates, **When** `list_stuck` runs, **Then** it returns one entry, for the earlier fired gate.
3. **Given** a goal in `awaiting_gate` whose only open gates are unfired, **When** `list_stuck` runs, **Then** the goal is not listed as stuck at a gate and nothing raises.
4. **Given** an active goal idle past the threshold, **When** `list_stuck` runs, **Then** its entry is unchanged from today.
5. **Given** `last_stuck_alert_at` inside the cooldown, **When** `list_stuck` runs, **Then** the goal is skipped, as today.
6. **Given** the dev-database shape (one open gate, six unfired), **When** `StuckGoalJob` runs with a recording notifier, **Then** it sends one alert and marks the goal alerted.

---

### User Story 3 - Loops carry the evidence they came from (Priority: P1)

A loop made from a conversation turn, an email, or an ingested document is linked to that source. The push grounding check then compares the loop to what the user actually said, dropping a loop is remembered against its evidence, and a second "I need to…" about the same thing reinforces the loop instead of creating a duplicate.

**Why this priority**: Evidence is what the decay cascade, grounding, dismissal and the later corroboration phase (172) all stand on. Today every gate-created loop has none.

**Independent Test**: With fake stores, a conversation admission commits a loop whose store call receives one `episode` evidence ref. In the harness, create a loop with an episode ref, call `LoopSurfacer.passes_push_bar` with an NLI stub that returns low entailment for the rationale and high entailment for the title, and assert the bar passes on the title.

**Acceptance Scenarios**:

1. **Given** a positive conversation gate, **When** the commit runs, **Then** the created loop is linked to the turn's episode id and creation does not fail the dangling-evidence check.
2. **Given** an email, **When** the messenger processor handles it, **Then** the loop it creates is linked to the episode written for that message.
3. **Given** an ingestion, **When** the sink pushes facts, **Then** the loop is linked to the `ingestion` ref.
4. **Given** a calendar reminder, **When** the extractor runs, **Then** the loop is created with no evidence and the log line says why.
5. **Given** a loop with episode evidence and a drift rationale, **When** `passes_push_bar` runs, **Then** grounding compares the loop title to the evidence text, not the rationale.
6. **Given** the user dropped a loop with evidence E, **When** a later turn matches it with the same evidence E, **Then** no loop is created; **when** it arrives with a new episode, **then** a new `suspected` loop is created.
7. **Given** an `active` loop and a second declared obligation that matches it, **When** the declared path runs, **Then** no second loop is created, the new evidence is linked, and the drift deadline moves.
8. **Given** the episode write fails, **When** the commit runs, **Then** the loop is created without evidence and a warning is logged (fail open).

---

### User Story 4 - The priority page says what it could not load (Priority: P2)

When the goal source fails, the user today sees a ranking with no goals and no explanation. After this phase the response lists failed sources and the page says "Goals unavailable". Relationship items no longer break the response.

**Why this priority**: A silent partial view is how F3 hid. This is also a small fix for a real 500.

**Independent Test**: A TestClient call with a fake view whose ranking has a `relationship` item returns 200 with the item; a ranking with `sources_failed = {"goal"}` returns `sources_failed: ["goal"]`. A vitest test renders the notice.

**Acceptance Scenarios**:

1. **Given** a ranking with a relationship item, **When** the snapshot route runs, **Then** it returns 200 and the item has `source_kind: "relationship"`.
2. **Given** `sources_failed = {"goal"}`, **When** the route runs, **Then** the body is `{items, sources_failed: ["goal"]}`.
3. **Given** all sources fail, **When** the route runs, **Then** behavior is unchanged (`ZePriorityError`, as today).
4. **Given** the web page receives a non-empty `sources_failed`, **When** it renders, **Then** a visible notice names the unavailable sources.
5. **Given** the generated client, **When** `make codegen` runs, **Then** the committed generated files match the new response.

---

### User Story 5 - Dead pieces and false switches are gone (Priority: P2)

Config that nothing reads and code that nothing calls is removed or wired, so a reader of `config.yaml` can trust a flag.

**Why this priority**: Pre-v1 hard cuts. A flag that does nothing is how `correlation.push.enabled: false` still pushed.

**Independent Test**: Unit tests for each wired switch; graphify `affected` shows no non-test callers for each deleted symbol before deletion.

**Acceptance Scenarios**:

1. **Given** `worldstate.push.enabled: false`, **When** the arbitration job runs, **Then** it collects no loop candidates.
2. **Given** `worldstate.push.thresholds` and `inline_cooldown_hours`, **When** the job runs, **Then** `eligible_candidates` receives them.
3. **Given** `correlation.push.enabled: false`, **Then** hypothesis candidates are empty; **given** `enabled: true, dry_run: true`, **then** they are empty and a dry-run line is logged; **given** `enabled: true, dry_run: false`, **then** the existing push bar applies.
4. **Given** the codebase, **Then** `ze_memory.surfacing` (`SurfacingGate`, `SurfacingConfig`), `ze_priority.learning_context`, `LoopSurfacer.inline_candidates`, `DriftingLoopMention` and `worldstate.drift.window_days` no longer exist, with their tests.

---

### User Story 6 - Real-database tests stop this class of defect (Priority: P1, foundational)

A maintainer runs `make test-pg` and gets the SQL predicates and joins that matter run against real rows, in a throwaway database that is migrated by the real migration runner. Running `make test-py` does not need Docker.

**Why this priority**: F1, F3 and the 168 finding are the same defect three times. Without a harness the fixes would be untestable and the next one would ship the same way.

**Independent Test**: `make test-pg` passes with Docker; `make test-py` passes and reports the pg tests as skipped with a reason when Docker is absent or `ZE_TEST_PG` is unset; with `ZE_TEST_PG=1` and no Docker the run fails with one clear message.

**Acceptance Scenarios**:

1. **Given** Docker, **When** `make test-pg` runs, **Then** a container starts, migrations apply, the tests run, and the container is removed even when a test fails.
2. **Given** `ZE_TEST_PG_URL`, **When** `make test-pg` runs, **Then** no container is started and the harness uses a fresh schema in that database.
3. **Given** neither, **When** `make test`, `make test-py` or `make test-all` runs, **Then** pg tests are skipped, not failed.
4. **Given** the F1, F3 and F9 regression tests, **When** each fix is reverted, **Then** its test fails (fail-first).

---

### Edge Cases

- Concurrent `record_corroboration` and the sweep on one loop: both are single-row updates; the sweep's `transition` re-reads state, so a loop corroborated first is not drifted, and one drifted first stays drifting (corroboration touches `active` only).
- A loop with `drift_deadline` NULL and state `active` (rows created before 110): never a candidate, as today.
- `write_episode` returns `None` (embedding missing, insert failure): the commit proceeds with no episode ref.
- The turn's episode write finishes after the commit starts: the commit awaits the episode task before linking, inside its own background task, so the reply is never delayed.
- Evidence kind `episode` on the declared path needs the existence checker; the declared path passes the same checkers as the suspected path.
- `list_stuck` with `idle_days=0` (used by `PriorityView`): a freshly fired gate has 0 idle days and is still a goal row.
- A goal whose status is `awaiting_gate` but has no open gate at all: not returned as stuck at a gate; logged once per call at debug.
- `sources_failed` present but `items` empty: the page shows the notice and the empty state.
- Relationship items cannot be pinned or reordered by id collision: ids are `uuid5` of the name (unchanged).
- Generated client drift: `make codegen` output must be committed; CI-style check is the test that imports the type.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `LoopStore.list_drift_candidates` MUST select loops with `state = 'active' AND drift_deadline IS NOT NULL AND drift_deadline <= now()` and MUST NOT read `updated_at` or `confirmed_at`.
- **FR-002**: `LoopStore` MUST gain `record_corroboration(loop_id, *, window_days=DEFAULT_DRIFT_WINDOW_DAYS)`. For an `active` loop it sets `drift_deadline = GREATEST(COALESCE(drift_deadline, now()), now() + window)` and `updated_at = now()` in one statement; for any other state it changes nothing and returns without error. Contract: `contracts/drift-and-corroboration.md`.
- **FR-003**: `drift.is_drift_eligible` MUST match FR-001 (active, deadline set, deadline not after now). `DriftSweepJob` MUST rely on the store filter plus `is_drift_eligible` and MUST NOT use `is_stale`.
- **FR-004**: `compose_absence_rationale` MUST describe the elapsed window without claiming a confirmation date (the deadline can have moved): "No corroborating evidence (email, calendar, or conversational update) before the implied window elapsed on <date>."
- **FR-005**: Corroboration MUST be recorded when a re-extraction matches an existing `active` loop with at least one new evidence ref (suspected path and declared path). Creating a loop, linking its own first evidence, and the decay cascade MUST NOT call `record_corroboration`.
- **FR-006**: `PostgresGoalStore.list_stuck` MUST return at most one `awaiting_gate` entry per goal, built from the earliest fired open gate (`status IN ('pending','awaiting_approval') AND fired_at IS NOT NULL`), MUST ignore unfired gates, and MUST NOT raise for goals with unfired gates. A `fired_at` of NULL that reaches Python MUST be skipped with a warning, never dereferenced.
- **FR-007**: The active-goal half of `list_stuck`, the cooldown rule and the result ordering MUST be unchanged.
- **FR-008**: `PostgresMemoryStore.write_episode` (and the `MemoryStore` Protocol) MUST return the new episode `UUID`, or `None` when nothing was written. Existing callers MUST keep working unchanged.
- **FR-009**: `LoopAdmission.commit` MUST accept the evidence refs for the commit: `commit(evidence: Sequence[EvidenceRef] = ())`. `write_memory` MUST obtain the turn's episode id from the episode task, inside the existing fire-and-forget commit wrapper, and pass `[EvidenceRef("episode", id)]` when it is not `None`. The node MUST NOT wait for the episode task before returning.
- **FR-010**: `LoopInflow.extract(text, provenance, evidence=())` and the callables from `make_loop_extractor*` MUST accept an optional `evidence` argument. The messenger processor MUST pass the episode id returned by its `write_episode` call; the ingestion sink MUST pass its `ingestion` ref when the id parses as a UUID; the calendar job MUST pass none.
- **FR-011**: `propose_loop_candidates` MUST link the evidence it is given on every create and match path, and the declared path MUST pass the same existence checkers as the suspected path.
- **FR-012**: The declared path MUST call `find_matching_loop` over `suspected`, `active`, `drifting` before creating. On a match it MUST link the new evidence and entities and call `record_corroboration`, MUST NOT change the matched loop's state or confidence, and MUST NOT create a second loop.
- **FR-013**: `LoopSurfacer.passes_push_bar` MUST run the grounding check on the loop title against the evidence texts. Novelty MUST keep using the rationale. `_fetch_evidence_summaries` MUST give a usable text for `messenger` episodes (prompt plus the first 500 characters of the body).
- **FR-014**: The dismissal rule MUST be documented in code and tests as: suppress an inferred loop that matches a dropped loop iff the new evidence set fingerprint equals the dropped loop's stored fingerprint. Both evidence-less (e.g. calendar) suppresses; different evidence does not.
- **FR-015**: `PriorityView.rank()` MUST keep per-source degradation, and `ze_priority.rest.get_snapshot` MUST return the merged items together with `sources_failed`. `GET /api/v0/priority/snapshot` MUST return `PrioritySnapshotResponse {items, sources_failed}`. Contract: `contracts/priority-snapshot.md`.
- **FR-016**: Every `source_kind` and anchor kind in the priority REST schemas MUST accept `relationship`. A snapshot containing a relationship item MUST return 200.
- **FR-017**: `@myguyze/ze-client` generated files MUST be regenerated (`make codegen`) and committed. `ze-web` MUST read `{items, sources_failed}`, label relationship items, and show a notice when `sources_failed` is non-empty.
- **FR-018**: `AttentionArbitrationJob` MUST receive the loop push settings (`enabled`, `thresholds`, `inline_cooldown_hours`) from `compose.py` and pass them to `LoopSurfacer.eligible_candidates`. `worldstate.push.enabled: false` MUST yield no loop candidates.
- **FR-019**: `CorrelationPushCandidateSource.eligible_candidates` MUST return no candidates when `correlation.push.enabled` is false, and MUST log `correlation_push_dry_run` and return none when `dry_run` is true.
- **FR-020**: These MUST be deleted, with their tests, after `graphify affected` shows no non-test callers: `ze_memory/surfacing.py`, `ze_priority/learning_context.py`, `LoopSurfacer.inline_candidates`, `DriftingLoopMention`, and the `worldstate.drift.window_days` key.
- **FR-021**: A pytest marker `pg` MUST exist in `apps/ze-api/pyproject.toml`. Tests marked `pg` MUST be skipped unless `ZE_TEST_PG=1`. `make test-pg` MUST set it. `make test`, `make test-py` and `make test-all` MUST NOT require Docker. Contract: `contracts/pg-harness.md`.
- **FR-022**: The harness MUST start a throwaway `pgvector/pgvector:pg16` container (or use `ZE_TEST_PG_URL`), apply the real migrations with `ze_api.migrate.upgrade`, give each test module a clean database state, and remove the container at teardown.
- **FR-023**: There MUST be one regression test per finding (F1, F3, F9, F13) that fails when its fix is reverted, plus the two acceptance runs (Success Criteria SC-001, SC-002).
- **FR-024**: Default tests MUST NOT call OpenRouter or System One. The harness tests use fakes for the embedder, NLI client and relevance model.
- **FR-025**: There MUST be no schema migration and no change to `OpenLoop` or `StuckGoal` fields.

### Key Entities

- **Drift candidate**: an `active` loop whose `drift_deadline` has passed. The only input is the deadline.
- **Corroboration**: a new evidence ref arriving for an `active` loop. It moves the deadline; it does not change state or confidence.
- **Source evidence**: the `EvidenceRef` of the record a loop came from (`episode` or `ingestion`).
- **Open gate**: a goal gate with status `pending` or `awaiting_approval` and a non-NULL `fired_at`.
- **PrioritySnapshotResponse**: `items` (merged ranking rows) plus `sources_failed` (source kinds that could not be read).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (acceptance run A): On a migrated scratch database, a loop declared with a 1-day window, with its deadline moved into the past, is `drifting` after one `DriftSweepJob.run()`, ranks with the drift bonus in `PriorityView.rank()`, and is returned by `LoopSurfacer.eligible_candidates()` when the relevance, novelty and grounding collaborators accept it.
- **SC-002** (acceptance run B): On the same database, a goal with one fired `awaiting_approval` gate and three unfired gates appears exactly once in `PriorityView.rank()` with `sources_failed` empty, and `GET /api/v0/priority/snapshot` lists it.
- **SC-003**: For loops created by each of the conversation, email and ingestion paths in a test run, 100 percent have at least one evidence ref; calendar loops have none and the run logs it.
- **SC-004**: After a user drops a loop, the same evidence set does not create another loop (0 of N replays), and a new episode does (1 of 1).
- **SC-005**: `GET /api/v0/priority/snapshot` returns 200 for every combination of source kinds, including `relationship`, and reports every failed source (0 silent source failures).
- **SC-006**: `make test-py` passes with Docker stopped; `make test-pg` passes with Docker running; each regression test fails when its fix is reverted.
- **SC-007**: No key in `apps/ze-api/config/config.yaml` under `worldstate` or `correlation.push` is unread (each is read by code or deleted), shown by a test that loads the shipped config.
- **SC-008**: All existing suites touched (`test-worldstate`, `test-priority`, `test-automation`, `test-memory`, `test-core`, `test`, `test-web`, `typecheck-web`, `lint`) pass.

---

## Assumptions

- **Phase 169 lands first.** 170 implementation begins after 169 is on `main`. The first implementation task re-reads the 169 diff for `PostgresLoopStore.transition(user_asked)` and `stamp_declared`, and adapts only if 169 differs from its pinned spec (96d9de22). 170 does not edit `transition` or `stamp_declared`; it adds `record_corroboration` and changes `list_drift_candidates`.
- **Default window.** `record_corroboration` uses the 7-day `DEFAULT_DRIFT_WINDOW_DAYS`. A loop with a longer implied window keeps its longer deadline (`GREATEST`).
- **Dev database is not a fixture.** Tests build their own rows. The dev database is only used by the maintainer for a final manual check after the acceptance runs, read-only.
- **Contradiction-driven drift stays rare.** Episode and ingestion evidence do not feed the fact-contradiction cascade, which is keyed to `fact` refs. Absence drift is the main drift path after this phase.
- **Calendar loops stay evidence-less** until a calendar record with a stable UUID exists.
- **Resurfacing after a drop.** A new message about a dropped topic may re-suspect it (user accepted 2026-10-12).
- **The web change is small** (one hook, one widget, one label map). It is a `[WEB]` task, not a redesign.
- **No System One or Haiku behavior changes.**
