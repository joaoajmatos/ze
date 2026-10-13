# Research: Executive Repair

Evidence labels as in `specs/arch/executive-function.md`: **[code]** read in tree, **[scratch]** run against a throwaway Postgres, **[dev-db]** read-only SQL on the dev database.

## R1. Fix F1 without a new column

**Finding [scratch]:** `PostgresLoopStore.create` writes `confirmed_at` from Python, then `set_drift_deadline` runs `UPDATE ... updated_at = now()`; `transition` to `active` also sets `updated_at = now()`. `list_drift_candidates` requires `updated_at <= confirmed_at`. Observed `updated_at - confirmed_at` = 7.8 ms (declared path) and 1.4 ms (confirm path); candidates returned: `[]`.

**Options**
1. *`last_activity_at` column (zw003), predicate on it.* Explicit, but needs a migration, a backfill, and a rule for every writer that should or should not touch it. Keeps the old flaw: one early touch exempts a loop from drift forever, because the predicate compares against `confirmed_at`.
2. *Move the deadline on corroboration, drift = deadline passed.* **Chosen.** No schema change. The only input to the sweep is `drift_deadline`. Corroboration is the one operation that pushes it out (`record_corroboration`). No coupling to `updated_at`. Also fixes the exemption flaw (a corroborated loop drifts again after another window).
3. *Compare against a SQL `statement_timestamp` tolerance.* Rejected: hides the coupling.

**Why not extend the deadline in `link_evidence`:** `_create_declared_loop` links its own first evidence right after creating the loop. Extending there would overwrite an implied window shorter than 7 days at birth. Hence an explicit method, called only on re-extraction against an existing match.

**Compatibility with 169.** `stamp_declared` sets `confirmed_at`, `updated_at`, `drift_deadline`, `confidence`, `drift_rationale` in one statement. Option 2 ignores `confirmed_at` and `updated_at`, so a revived loop is a candidate when its new deadline passes. The 169 spec (96d9de22) is the authority for the revive field set; 170 does not edit it.

**Sweep rationale text.** The absence rationale cited "since confirmation on <date>". With extensions that is not true, so FR-004 rewords it.

## R2. Real-Postgres harness: how it runs

**Constraint:** `make test-py` and `make test-all` must not require Docker. **Requirement:** SQL predicates and joins run against real rows with the real migrations.

**Where the tests live.** `apps/ze-api/tests/pg/`. `ze-api` already depends on every package under test (`ze_worldstate`, `ze_automation`, `ze_priority`, `ze_memory`) and owns the migration runner (`ze_api.migrate`, which merges all package chains). Package suites cannot import `ze_api`. One harness, one place.

**Selection.** Marker `pg` (new, registered in `apps/ze-api/pyproject.toml`; the existing `integration` marker is unused and means "a running database", so it is not reused). A `conftest.py` in `tests/pg/` skips every `pg` item unless `ZE_TEST_PG=1`, with the reason "set ZE_TEST_PG=1 (make test-pg) to run real-Postgres tests". `SLOW=1`/`test-all` do not set it. Result: default runs collect and skip; no Docker call is made at collection time.

**Database.** Preferred order: (1) `ZE_TEST_PG_URL` (asyncpg URL) if set, using a fresh schema per session; (2) a throwaway container: `docker run -d --rm -p 127.0.0.1::5432 -e POSTGRES_PASSWORD=ze pgvector/pgvector:pg16`, port read from `docker port`, readiness by `pg_isready` retry. Image `pgvector/pgvector:pg16` is the one `docker-compose.yml` uses and the memory migrations need `vector`. Plain `postgres:16-alpine` is not enough for the full chain.

**Migrations.** `ze_api.migrate.upgrade(sync_url)` once per session (psycopg2 URL, same as `make migrate`). Real schema, not hand-written DDL, so a column or constraint change breaks the tests (the point). Expect a few seconds.

**Isolation.** Session-scoped container and migration; function-scoped `pg_pool` fixture that `TRUNCATE ... RESTART IDENTITY CASCADE` the tables the tests touch (`open_loops`, `memory_relationships`, `memory_episodes`, `goals`, `goal_gates`, `goal_milestones`, `push_log`, `correlation_hypothesis`, `priority_overrides`). A fixed list in one helper, not a catch-all, so a new table is a visible decision.

**Teardown.** `docker stop` in a session-finalizer and `atexit`; `--rm` removes the container. A failed test never leaves it running. If `docker` is missing and `ZE_TEST_PG=1`, fail once with one message (do not skip: the user asked for the run).

**No new dependency.** The container is driven with `subprocess` and `docker` CLI. No `testcontainers` package.

**Make target.** `make test-pg`: `ZE_TEST_PG=1 uv run pytest -q -m pg apps/ze-api/tests/pg`. Added to `.PHONY`, `make help`, and `docs/testing.md`; deliberately not in `TEST_PY_PACKAGES`.

**CI.** Out of scope here. The target is the entry point if CI wants it later.

## R3. F3: one row per goal

**Finding [dev-db], [code]:** The gate query joins `goal_gates vg ON vg.goal_id = g.id AND vg.status IN ('pending','awaiting_approval')`. Gates are created up front; later ones stay `pending` with `fired_at NULL`. The dev goal "AI Engineering Weekly Report" has 1 `awaiting_approval` gate and 6 `pending` unfired ones. `fired_at.tzinfo` raises on the first unfired row. Even with no NULL, the join yields one row per open gate.

**Fix.** `DISTINCT ON (g.id)` ordered by `g.id, vg.fired_at ASC`, with `vg.fired_at IS NOT NULL` in the join. Keep the Python `is_stale` check and add a defensive `if fired_at is None: continue` with a warning. Order of results is re-sorted by `idle_days` in Python as today.

**Why not fix the model (gates only exist when fired).** Gates are planned up front on purpose (goal planner). Query fix only.

**Test data.** The harness inserts via the goal store's own create methods where they exist and raw `INSERT` for backdating `fired_at`. The dev shape (1 open, 6 unfired) is the primary case.

## R4. F9: where evidence comes from

**Finding [code]:** `LoopInflow._commit_for` passes `evidence_refs=[]`. The extractor callable signature is `(text, provenance)`, so callers could not pass any. No inflow had the id to pass either.

| Inflow | Source record | Id available? | Decision |
|---|---|---|---|
| conversation | `memory_episodes` row written by `write_memory` | `PostgresMemoryStore.write_episode` already does `INSERT ... RETURNING id` and drops it | return it; node awaits the task inside the commit wrapper |
| email | `write_episode(session_id=msg.message_id, ...)` in `InboundMessageProcessor` (awaited just before the extractor task) | same | pass it |
| ingestion | `ingestion_id` string, parsed to `UUID` in `MemorySink.push` | yes | pass `EvidenceRef("ingestion", uuid)` |
| calendar | `signal.external_ref` (string, not a UUID) | no | none; documented gap |

**Why not extend `EvidenceRef.kind`** (add `calendar_event`): `EvidenceRef` is a ze-plugin contract used by the seam; widening it for one inflow is a doctrine-level change, out of scope. Calendar can write an episode later (Phase 173) or gain a kind with its own spec.

**Dangling check.** `validate_and_submit` rejects an `episode` ref without `check_episode_exists`. `_create_declared_loop` passes no checker today; it gets the same two checkers as the suspected path. The `ingestion` kind is skipped by design.

**Race.** `write_memory` fires `write_episode` as a background task. The loop commit is also a background task. The commit awaits the episode task first, then creates the loop with the id. The reply is not delayed. If the episode task failed, the commit creates the loop without a ref (fail open, FR-011 scenario 8).

**Contradiction cascade stays narrow.** `cascade_from_evidence("fact", id, ...)` is keyed to `fact` refs. Episode and ingestion evidence do not make contradiction drift fire. They enable grounding, the fingerprint, and Phase 172's corroboration counting. This is stated so no one expects more.

## R5. F9: the grounding gate would block everything

**Finding [code]:** `passes_push_bar` calls `passes_grounding(rationale, evidence_labels, nli, threshold)`. The rationale for a sweep-drifted loop is an absence statement ("No corroborating evidence ... implied window elapsed"). Evidence labels are what the user said. NLI entailment of an absence from a statement is low by nature. Today the gate passes because `evidence_labels` is empty (`passes_grounding` returns true when there are no labels). Linking evidence turns a vacuous pass into a near-certain fail.

**Fix.** Ground the *loop title* ("renew passport before the March trip") against the evidence texts. That is the question the gate was meant to ask: is this loop grounded in something the user said. Novelty keeps the rationale (it compares push text to recent pushes). The threshold (0.3 in `_DEFAULT_THRESHOLDS`; `0.5` in the unread `worldstate.push.thresholds`) stays where it is; R6 wires the config, so the shipped 0.5 would start applying. **Decision:** wire the config but set the shipped `grounding_threshold` to 0.3 (the value code actually ran with) so enabling the config does not tighten the bar silently. Recorded in the task and in the DOCS note.

**Evidence text for emails.** The email episode has `prompt = "[Inbound email from X] Subject: ..."` and the body in `response`. `_fetch_evidence_summaries` uses `COALESCE(summary, prompt)`, which for email yields only the subject line. For `agent = 'messenger'` use `prompt || ' ' || left(response, 500)`.

## R6. Config that nothing reads

[code] Findings from grep:

| Key | Read by | Decision |
|---|---|---|
| `worldstate.push.enabled` | nothing | wire: gate the loop half of `AttentionArbitrationJob` |
| `worldstate.push.inline_cooldown_hours` | nothing (`LoopSurfacer` default 12) | wire |
| `worldstate.push.thresholds` | nothing (defaults hardcoded) | wire; shipped `grounding_threshold` 0.3 (R5) |
| `worldstate.drift.window_days` | nothing (`DEFAULT_DRIFT_WINDOW_DAYS` constant) | delete the key; the constant stays |
| `correlation.push.enabled`, `dry_run` | `CorrelationPushConsumer.run_once` only | honor in `CorrelationPushCandidateSource.eligible_candidates` (FR-019) |
| `correlation.salience.surfacing.tau_push`, `tau_inline`, `tau_relevance`, `novelty_similarity_max` | live code (`push.py`, `nodes/correlation.py`) | keep |
| `correlation.salience.feedback.*`, `correlation.salience.surfacing.min_evidence`, `budget` read by `SurfacingConfig` | only the dead `SurfacingGate` (grep at spec time found no other reader) | delete the keys with `SurfacingGate`; re-grep first |

**Behavior change to flag.** The shipped `correlation.push` is `enabled: false, dry_run: true`. Today the arbitration path ignores both, so a hypothesis passing the push bar can be pushed. After this phase none is pushed until the user sets `enabled: true, dry_run: false`. This is the config doing what it says.

## R7. Dead code to delete

[code] confirmed by graphify `affected` and grep at spec time; the implementer re-runs before deleting.

- `ze_memory/surfacing.py` (`SurfacingGate`, `SurfacingConfig`): imported only by `ze-memory/tests/test_salience.py`. Delete the module and every test that references `SurfacingGate`, `SurfacingConfig` or `_make_surfacing_gate` (sections at lines ~483 to 736 and ~770 to 798 of `test_salience.py`); keep the tests that exercise `RelevanceModel` demotion and `build_admission_gate_reads_salience_config`. Observation, not in scope: after the cut nothing writes the `demoted_topics`/`news_exclusions` facets that `RelevanceModel.build()` reads; record it in the PR description for a later cleanup.
- `ze_priority/learning_context.py` and `tests/test_learning_context.py`: no production caller.
- `LoopSurfacer.inline_candidates` and `DriftingLoopMention`: superseded by `TurnSurfacing` (Phase 132). Delete with the tests that cover them in `test_surfacing.py`.
- `OpenLoop.goal_id`: **kept.** Removing the column is a migration, and Phase 173 may use it for link rows.

## R8. Priority snapshot response and F13

**Finding [code]:** `schemas.PrioritySnapshotItem.source_kind: Literal["loop","goal","hypothesis"]`, but `ze_priority.types.SourceKind` includes `"relationship"` and `container.py:680` wires the source. [verified] pydantic rejects `"relationship"` for that Literal, so the route would fail response validation whenever `PersonStore.list_stale_for_follow_up` returns a nudge.

**Shape.** Hard cut: `{ "items": [PrioritySnapshotItem], "sources_failed": ["goal", ...] }`. One consumer (`usePrioritySnapshotQuery`). Mutation routes (`/override`, `/unpin`) keep returning a single `PrioritySnapshotItem`. `ze-client` is regenerated.

**Why not a response header.** Invisible to the generated client and to the page.

## R9. Declared-path dedup scope

[code] `_commit_admitted` → `_create_declared_loop` creates a loop with no `find_matching_loop`. 169's `track_loop` dedups its own path. For the gate path 170 adds the match-then-corroborate step only. It deliberately does **not** promote a matching `suspected` loop: that is a state change on the user's behalf and belongs to 169's tracker (explicit ask) and Phase 172 (corroboration bar).
