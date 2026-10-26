# Research: Open-Loop Lifecycle (phase 203)

All claims checked against `main` at `9529da15` (2026-10-26). 198 and 199 have landed. No worldstate file changed on `main` after the floor base `5426cce1`.

## R1. Module shape: a `lifecycle` package with pure rules and one event class

**Decision**: A new package `ze_worldstate/lifecycle/`:

- `rules.py`, pure: `LoopEvent` (a `StrEnum` of the fourteen events), `EventRule` (from-states, to-state, stamp), the `EVENT_RULES` table, `DeclaredStamp`, `check(event, state)`. No I/O.
- `events.py`: `LoopLifecycle`, one async method per event. Each method runs one transaction and returns the loop as stored. It owns every SQL statement that changes `open_loops`, the loop's `memory_relationships` rows and `open_loop_sources`.
- `__init__.py` exports `LoopLifecycle`, `LoopEvent` and `DeclaredStamp`. The commit decision lives in its own module (R6).

`PostgresLoopStore` keeps only reads: `get`, `list`, `list_by_evidence`, `count_evidence_links`, `list_evidence`, `list_drift_candidates`, `list_sources`, `list_sources_for`.

**Rationale**: The interface is the domain events (codebase-design: a deep module). The rules table is pure, so the SC-004 table test runs without a database. The SQL sits behind the event methods, so no caller can make half an event.

**Alternatives considered**:
- *Keep the writes on the store and add a thin lifecycle layer that calls them in a transaction.* Rejected: the store would still expose `set_confidence`, `transition` and the rest, against FR-007, and asyncpg transactions do not span the store's per-method `acquire()`.
- *One flat `lifecycle.py`.* Workable, but rules and SQL in one 600-line file make the table test import the SQL. Two files are cheap.

## R2. Atomicity: one transaction per event, guarded by state, with a row lock

**Decision**: Every event method does:

1. `async with pool.acquire() as conn, conn.transaction():`
2. A guarded write: `UPDATE open_loops SET … WHERE id = $1 AND state = ANY($allowed) RETURNING *`. The allowed states come from `EVENT_RULES`.
3. If no row comes back, one `SELECT state FROM open_loops WHERE id = $1` in the same transaction tells `LoopNotFoundError` (no row) from `InvalidLoopTransitionError` (wrong state). Both types exist today (`errors.py`); REST maps the second to 409.
4. The event's other writes (evidence links, entity links, source rows) in the same transaction.

**Row lock first.** Every event on an existing loop that writes more than one statement (drop, expire, track, note evidence, corroborate, promote, resolve) takes the loop's row lock first with `SELECT … FOR UPDATE`, before it reads evidence or writes links. Two events on one loop therefore never interleave: a drop cannot compute its fingerprint while a note-evidence is adding a link. Single-statement events (decay, drift, confirm, close, link) need no separate lock: the guarded `UPDATE` locks the row and reads its current state.

**No I/O inside a transaction.** Entity resolution, matching, embeddings, System One judgments and the title writer all run before the event is called. The event's transaction holds only SQL, so row locks last milliseconds.

Decay is one statement per loop:
`SET confidence = …, state = CASE WHEN state = 'active' THEN 'drifting' ELSE state END, drift_rationale = CASE WHEN state = 'active' THEN $r ELSE drift_rationale END`. A loop the sweep drifted a moment earlier is already `drifting`, so decay changes its confidence and leaves its state and rationale alone (US1 scenario 3).

The drift sweep's statement keeps the deadline guard: `WHERE id = $1 AND state = 'active' AND drift_deadline <= now()`. A loop confirmed again between the candidate read and the write is not drifted.

**Rationale**: Postgres evaluates the `WHERE` guard against the row it locks, so a guarded `UPDATE` is atomic without extra locking. The existing `transition()` already uses `AND state = $5`. `resolve()` (199) already uses a transaction.

**Alternatives considered**: Advisory locks per loop (more moving parts, no gain); `SERIALIZABLE` isolation (retries needed in every caller).

## R3. The declared stamp, defined once

**Decision**: `rules.DeclaredStamp` holds `CONFIDENCE = 0.9` (moved from `types.DECLARED_CONFIDENCE`, which is deleted), `DEFAULT_WINDOW_DAYS = 7` (`drift.DEFAULT_DRIFT_WINDOW_DAYS` is deleted and its readers import from `rules`), and one SQL fragment builder:

```text
confidence stamp(new)   -- the existing _CONFIDENCE_STAMP (prior + changed_at), moved here
confirmed_at = now(), drift_deadline = now() + make_interval(days => $w), drift_rationale = NULL
```

`stamp_sql(confidence_expr)` returns the fragment. Confirm, track (confirm and revive) and create declared pass `$c` with 0.9. Promote passes `GREATEST(confidence, $c)` with 0.7 (FR-004, phase 172). The window is a parameter: confirm and promote use 7 days, track uses the clamped `window_days`, an inflow declared create uses the title writer's `implied_window_days` or 7.

Create declared writes the stamp in its `INSERT` (`confirmed_at = now()`, `drift_deadline = now() + window`, rationale NULL, confidence 0.9). The `INSERT` and the `UPDATE` take the same constants from `DeclaredStamp`, and a test asserts both produce identical rows (SC-002).

**Behavior note**: the inflow declared path computes its deadline in Python today (`compute_drift_deadline(confirmed_at, …)`). It moves to the database clock. The difference is the clock skew between the API process and Postgres, which on one machine is nil. `drift.compute_drift_deadline` is deleted.

**Rationale**: SC-002 counts places that define the stamp; four become one.

## R4. The rules table

**Decision**: `EVENT_RULES` (data-model.md has the full table). The rules FR-003 names:

- `active → drifting`: only `DECAY` and `DRIFT`.
- `drifting → active`: only `TRACK` (the user asked). `CONFIRM`, `DECAY`, `DRIFT` and the REST confirm route cannot revive. This replaces `_USER_ASKED_TRANSITIONS` and the `user_asked=` flag.
- `suspected → closed`: only `RESOLVE`.
- `suspected → active`: only `CONFIRM`, `TRACK` and `PROMOTE`.

The generic `transition()` and `_ALLOWED_TRANSITIONS` are deleted. No caller can ask for a raw state move.

**Rationale**: The table is the rule. The SC-004 test walks every `(event, state)` pair: 14 events × 5 states = 70 rows, each asserting allowed or refused and the target state.

## R5. Creates go through the contribution seam, with the transaction as the writer

**Decision**: `create_suspected` and `create_declared` call `submit_and_detect_collisions(contribution, writer, …)` as today. The `writer` callback is the whole create transaction: the `INSERT`, evidence links, entity links and the origin source row. Both creates put the evidence on the contribution and pass the existence checkers built from `memory_store` (FR-005). `LoopLifecycle` takes `pool`, `memory_store`, `collision_store` and `nli_client` in its constructor.

`track_loop`'s create passes no evidence (the turn's episode does not exist when the tool runs) and an origin source `(conversation, <thread id>)`. The tool gets the thread id as `session_id: Injected[str | None]`: `session_id` is the LangGraph `thread_id` (`ze_core/conversation/turn.py:36-38`), and tools already receive it this way (`ze_automation/agents/workflow/tools.py:196`). With an origin row, a later suspected match from the same thread is not counted as independent corroboration (172's rule). Linking the turn's episode afterwards is deferred (spec Clarifications 2026-10-26).

Collision detection is unchanged: `submit_and_detect_collisions` starts it fire-and-forget after the writer returns (`ze_collision/detect.py:175-190`), so it can never roll back a committed create.

**Rationale**: The seam validates first and writes through the callback (`specs/arch/contribution-seam.md`), so the transaction fits inside it unchanged. Phase 212 (contribution submitter) depends on 203 and will find the loop submit sites in `lifecycle/events.py` instead of `extraction.py` and `tracking.py`.

## R6. One commit-decision vocabulary

**Decision**: A new module `ze_worldstate/decision.py`:

```text
CommitKind = Literal["resolve", "create_declared", "create_suspected", "hold", "fallback"]
GateKind   = Literal["resolve", "create_suspected", "hold", "fallback"]   # what loop_judge.decide returns
@dataclass(frozen=True) CommitDecision(kind, reason, consumed=frozenset(), title=None, window_days=None)
```

- `loop_judge.decide` returns a `CommitDecision` whose kind is a `GateKind`; `LoopGateDecision` and `loop_judge.DecisionKind` are deleted (agreed with 202: 203 owns this entirely).
- `commitment_judge.OutcomeKind` uses the same three loop kinds: `resolve_loop` → `resolve`, `create_loop_declared` → `create_declared`, `create_loop_suspected` → `create_suspected`. `CommitmentIntake._apply` builds `CommitDecision(outcome.kind, outcome.reason, outcome.consumed)` directly. `_LOOP_KIND` is deleted (spec Clarifications 2026-10-26).
- The 109 Haiku gate produces a `CommitDecision` too: `extraction.decide_with_109_gate(text, llm, model)` maps `_ExtractionGateResult` to resolve, create declared, create suspected or hold, and carries `title` and `window_days` from the gate. A failed gate is `hold` with reason `gate_failed`.
- `title` and `window_days` are set only by the 109 gate. On the System One path they are empty and the commit asks the title writer.

`decision.py` is new so that `types.py` (which 202 also edits) gains no new type. `types.py` drops its import of `loop_judge`.

**Rationale**: FR-009 and SC-003. The remap goes; the gate subset is a type, so a test asserts `decide` never returns `create_declared`.

**Alternatives considered**: keep the intake strings and add a typed field. Rejected by the user (two names for one thing).

## R7. One loop-inflow commit method

**Decision**: `LoopInflow.commit(decision, *, text, inflow, evidence=(), source=None) -> CommitResult`.

- `hold`: writes nothing, returns `CommitResult(outcome="held", reason=decision.reason)`.
- `fallback`: runs the 109 gate (R6) once, then continues with its decision. A second fallback is impossible (the gate never returns one).
- `resolve` / `create_*` without a title: calls `write_loop_title`. No title → `CommitResult(outcome="no_title")`, nothing written (edge case).
- `resolve`: match a live loop; no match → `CommitResult(outcome="no_match")`, not an error; else `lifecycle.resolve`.
- `create_declared` / `create_suspected`: resolve entities, match (and for suspected, the dismissed-fingerprint check), then on a match the match flow (R10), else `lifecycle.create_*`.
- Any exception is caught and logged once (`loop_commit_failed`) and returns `CommitResult(outcome="error")`. The commit runs fire-and-forget, so it must never raise.

`CommitResult(outcome, reason, loops: tuple[OpenLoop, ...])` lives in `decision.py`.

Internal helpers take one frozen `_Commit` value (text, inflow, evidence, source, entity_ids, title, window_days) instead of threading parameters, so no function in the path takes more than 8 (SC-003). `propose_loop_candidates`, `_commit_admitted`, `_create_declared_loop`, `_create_suspected_loop`, `_close_matching_loop`, `_match_existing` and `commit_for` are deleted. The unreachable `provenance == "user_declared"` branch goes with them.

`LoopAdmission` (types.py) loses `commit` and gains `text` and `inflow` as constructor fields beside `source`, so the record is complete when built. `decision` becomes `CommitDecision`. 202's single `judgment` field is untouched.

`LoopInflow.extract` (email, calendar, ingestion) becomes: judge → log → `await self.commit(admission.decision, text=…, inflow=…, evidence=…, source=…)`.

**Rationale**: FR-008, FR-010, US3. `extraction.py` keeps the 109 gate, the title writer, `resolve_entities`, `_whole_days`, `_loads_json` and the existence checkers. `eval/calibration/loop_gate.py` imports `_run_extraction_gate`, `_SYSTEM_PROMPT`, `_ExtractionGateResult` and `_loads_json` from it, and `tracking.py` imports `resolve_entities` and `_whole_days`; those names stay.

## R8. `write_memory` calls the inflow's commit directly

**Decision**: `ZeContainer._build_config` adds `configurable["loop_commit"] = self.commitment_intake.loop_inflow.commit` beside `commitment_intake` (`apps/ze-api/ze_api/wiring/container.py:369-370`). `CommitmentIntake` exposes the inflow as a read-only property `loop_inflow`. `write_memory` replaces `loop_result.commit` with:

```text
loop_commit = configurable.get("loop_commit")
if loop_result is not None and loop_commit is not None and loop_result.decision.kind != "hold":
    fire_and_forget(_commit_with_episode(loop_commit, loop_result, episode_task), label="loop_commit")
```

`_commit_with_episode` reads `decision`, `text`, `inflow` and `source` off the admission by attribute (ze-core never imports ze-worldstate) and passes the episode as evidence.

**Rationale**: FR-010. One configurable key, one line in the container. Floor 201 (typed turn services) rewrites `_build_config` later and will carry the key into its services object.

**Alternatives considered**: `CommitmentIntake.commit_loop` delegating to the inflow (an extra hop the spec rules out); a bound commit on the admission (the closure FR-008 removes).

## R9. Forcing a failed second write on test-pg

**Decision**: The pg `conftest.py` creates, once per session, a test-only table `ze_test_faults(table_name text primary key)` and a trigger function that raises when `TG_TABLE_NAME` is listed in it. The trigger is attached `BEFORE INSERT OR UPDATE` on `open_loops`, `memory_relationships` and `open_loop_sources`. A test inserts the table it wants to fail, runs the event, catches the error, and asserts the loop row, its links and its sources are exactly as before. `ze_test_faults` is truncated with the other reset tables.

For single-statement events the test asserts every field the event stamps (SC-001 holds by construction); for multi-write events (both creates, drop, expire, track, note evidence, corroborate, promote, resolve) it forces the failure on the second table.

**Rationale**: No product code carries a fault hook. A session setting would not work: the lifecycle takes its own connection from the pool.

## R10. The match flow and corroboration

**Decision**: When a create matches an existing live loop:

- not suspected → `lifecycle.note_evidence(loop_id, evidence, entity_ids)`: links, and for an active loop with evidence the 170 deadline move, in one transaction.
- suspected → `Corroborator.on_suspected_match(existing, dropped, commit)` in `corroboration.py`. It keeps 202's judging code (`_judge`, the surface config block) and the pure `is_independent` / `corroborated_confidence`. Its effects become one lifecycle call each:
  - not judged, not independent, or judged no → `lifecycle.note_evidence`;
  - corroborate → `lifecycle.corroborate(loop_id, evidence, entity_ids, source=LoopSource(...), confidence=…)`: links, the corroboration source row, and the raised confidence; a duplicate source row (`ON CONFLICT DO NOTHING` returns nothing) writes no confidence and reports `duplicate_source`;
  - promote → `lifecycle.promote(loop_id, evidence, entity_ids, source=…)`: links, the source row with `promoted = true`, and the promote stamp guarded by `state = 'suspected'`. If the guard fails (another inflow promoted first), the source row keeps `promoted = false` and no confidence is written, and the outcome is `lost_race` (edge case: one promotion wins). Today the loser calls `set_confidence(corroborated)` on the loop the winner just promoted, which can lower 0.7 to at most 0.6 (`corroboration.py:195-199`); the lifecycle fixes that as part of the atomicity work (FR-013).

`corroborate_match` (11 parameters and a `link` closure) becomes `Corroborator`, built by `LoopInflow` with `lifecycle`, `loop_store` (reads), `system_one_client` and `settings`. `mark_source_promoted` and `add_source` leave the store.

**Rationale**: SC-003 and FR-002. Hunk split with 202: 202's judging lines move into the new method verbatim on rebase.

## R11. Wiring and injection

**Decision**:

- `bootstrap.build_worldstate_stack` builds `LoopLifecycle(pool, memory_store=shared.memory_store, collision_store=…, nli_client=shared.nli_client)` and adds it to `WorldstateStack.lifecycle` and `deps[LoopLifecycle]`. The collision store is wired after the stack exists today (`hooks.wire_collision_detection`); the lifecycle takes it the same way, as a late attribute set in that function, so the build order does not change.
- The `loops` agent tools (`confirm_loop`, `close_loop`, `drop_loop`) take `lifecycle: LoopLifecycle` instead of calling `review.*`. `review.py` is deleted. `track_loop` gains `session_id: Injected[str | None] = None`.
- `rest.py` confirm, close and drop take the lifecycle. `apps/ze-api/ze_api/api/deps.py` gains `get_loop_lifecycle`; the loops router uses it for the three write routes.
- `decay.py` is deleted. `hooks.install_contradiction_hook` calls `worldstate.lifecycle.decay_from_evidence("fact", fact_id)`.
- `DriftSweepJob` and `StaleSuspicionJob` take the lifecycle (for writes) and the store (for the candidate reads).
- `LoopTracker` takes the lifecycle and the store (matching reads).
- `CommitmentIntake._link_one` calls `lifecycle.link(...)`.

**Rationale**: Constructor injection (constitution IV). Floors 201 (`wiring/container.py`, `api/deps.py`, the `*Stack`s) and 204 (`ze_worldstate/bootstrap.py`, `build_loop_surfacer`) touch nearby lines; plan.md lists the hunks.

## R12. Tests

**Decision**:

- `core/cognition/ze-worldstate/tests/test_lifecycle_rules.py`: the 70-row table test (SC-004), and the stamp-defined-once check (SC-002: grep-style assertion that `0.9` and the stamp fragment appear only in `rules.py`).
- `apps/ze-api/tests/pg/test_loop_lifecycle_pg.py`: one test per event against real Postgres, plus the forced-failure test per multi-write event (SC-001), the decay-vs-sweep race, the two-promoters race, confirm on an active loop (409 type), decay on closed and dropped loops.
- `apps/ze-api/tests/pg/test_loop_commit_pg.py`: `LoopInflow.commit` with each decision, a fake title writer and System One off (US3), plus the SC-005 replay: seed suspected loops with evidence, drop one and let one expire, then replay the same texts and evidence through `commit` once per simulated day for 30 days (each day runs both sweeps with `created_at` and deadlines shifted back a day). No dropped loop comes back.
- `_builders.make_loop` seeds rows with plain SQL (`INSERT … RETURNING *`), because the store loses `create` and seed rows are not lifecycle events.
- The existing pg tests that call removed store writes (about 60 calls in 14 files) move to lifecycle events or `make_loop`.
- Unit tests for callers (`test_tracking.py`, `test_admission.py`, `test_intake.py`, `test_corroboration_flow.py`, jobs) mock `LoopLifecycle` with `AsyncMock(spec=LoopLifecycle)` instead of the store. Mocked-store tests that only tested ordering are deleted (FR-012).

**Rationale**: FR-012, constitution V.

## R13. No migration

**Decision**: No schema change. Atomicity comes from transactions on the existing tables (`open_loops`, `open_loop_sources`, `memory_relationships`). If one turned out to be needed, the next free revision on the worldstate chain is `zw007`.

## R14. Doctrine function and eval

**Decision**: The phase serves **executive function** (world-state is the spine: open loops are Ze's model of unfinished business). No eval scenario is added; `eval/scenarios/loops.yaml` is the live regression (optional, costs credits). The calibration runners change only their kind literals (R6), after rebasing on 202.

## R15. Trace and web

**Decision** (spec Clarifications 2026-10-26): the `intake_outcome` trace row's answer becomes `resolve:…`, `create_declared:…`, `create_suspected:…`. `apps/ze-web/src/widgets/assemble/lib/instruments/judgments.ts:84-86` maps the new keys to the same sentences; its test rows change with it. Old stored traces show the raw key (pre-v1 hard cut).
