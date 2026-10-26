# Research: Push Bar and Cooldowns

**Phase**: 204 | **Date**: 2026-10-26 | **Base**: main `5426cce1` (198 and 199 landed)

Every decision below was checked against the code on main. File references are to that commit.

## R1. Where the push bar lives, and who applies it

**Decision**: one `PushBar` class in `ze_priority/push_bar.py`. `AttentionArbitrationJob` applies it to the candidates each source returns. Sources (`LoopSurfacer`, `CorrelationPushCandidateSource`) only build `PushCandidate` values and send the one the job picks. The candidate value type and the thresholds type live in `ze_proactive/candidates.py`, so ze-worldstate and ze-correlation can build candidates without importing ze-priority.

**Rationale**:

- The dependency graph runs `ze-priority → ze-worldstate, ze-correlation`. The bar needs "mentioned inline recently" from `TurnSurfacing` (FR-010), which is in ze-priority. A bar in ze-correlation (its home today) or ze-worldstate could not read it without an upward import.
- ze-priority already owns attention arbitration and the job that ranks the candidates (`arbitration.py`). Applying the bar there makes FR-003 structural: a source has no bar to call.
- Both sources already depend on ze-proactive (they call `notify`), so a candidate type there adds no edge.
- SC-005: a new source is a class with `source_kind`, `thresholds`, `dry_run`, `candidates()` and `send()`. Neither the bar nor the job changes.

**Alternatives considered**:

- Keep the bar in ze-correlation as a class. Rejected: it cannot reach `TurnSurfacing` without an upward import, and ze-worldstate would keep its only reason to depend on ze-correlation.
- Put the bar in ze-proactive. Rejected: the bar needs the embedder and NLI, and ze-proactive is a contract package for scheduling and the governor, not judgment.

## R2. Where the cooldown is answered, and how it is atomic

**Decision**: the governor's own claim table, `push_log`, answers every cooldown and every budget count. `PushLogStore.claim(...)` runs one transaction:

1. `pg_advisory_xact_lock(hashtext('push_log:key:' || claim_key))`;
2. for a discretionary push, also `pg_advisory_xact_lock(hashtext('push_log:budget'))` (always taken second, so two claims never wait on each other in a cycle);
3. look for a row with the same `claim_key` inside the window (or ever, when there is no window) → `cooling`;
4. for a discretionary push, count discretionary rows in the last 24 hours → `over_budget` when the count has reached the cap;
5. otherwise insert the row and return `won` with its id.

The notifier keeps the row for `delivered` and `held`, and deletes it by id for `failed` (persist or delivery error). `over_budget` inserts nothing, so `suppressed_budget` never starts a cooldown.

**Rationale**:

- FR-006 needs the check, the record and the budget claim in one step. Only a claim taken inside one transaction gives that. `notifications` rows are written after the governor decides, so two racing runs could both see "nothing sent".
- The advisory lock gives "at most once per key per rolling window" with append-only rows, and release is a delete by id. A unique index cannot express a rolling window.
- The budget lock also makes the daily cap exact. Today `within_budget` and `try_claim` are separate statements (`attention_budget.py:52-58`), so two racing claims can overrun by one. Ze is single-user; serialising discretionary claims costs nothing.

**Alternatives considered**:

- Answer the cooldown from `notifications` filtered on `delivery IN ('delivered','held','released')`. Rejected: not atomic (above), and `notifications` is pruned by its own retention rule.
- One row per key with `INSERT … ON CONFLICT DO UPDATE … WHERE sent_at < now() - window`. Rejected: releasing a failed claim must restore the previous timestamp, which needs a second read and makes the row mean two things.
- Keep a unique index and put the window into the key (`loop:<id>:<iso week>`). Rejected: a fixed bucket is not a rolling window; a push on Sunday and Monday would both pass.

## R3. One claim concept: `once_per` absorbs `budget_key`

**Decision**: `notify(..., once_per: OncePer | None)` with `OncePer(key: str, within: timedelta | None = None)`. `within=None` means once ever, which keeps today's behaviour for the ten discretionary callers whose keys already name a unique thing (`insight:<id>`, `inbound:<channel>:<message>`, `finance_stale:<account>:<date>`, …). Discretionary pushes must pass `once_per` (`PushPolicyError` otherwise, as `budget_key` is required today). Requested pushes must not pass it (`PushPolicyError`; FR-009). Accountability pushes may pass it. `budget_key`, `dedup_hours` and the `duplicate` outcome go; a repeated key returns `deduped`.

The loop source passes `OncePer(f"loop:{id}", within=timedelta(days=repush_after_days))` (Clarifications Q1). The hypothesis source passes `OncePer(f"hypothesis:{id}")`.

**Rationale**: today two concepts answer one question ("has this already gone out?"): `budget_key` (discretionary, forever) and `dedup_hours` (unused). The forever rule is the 198 Q4 bug. One concept with an optional window fixes the loop case and keeps every other caller's behaviour.

**Alternatives considered**:

- Keep `budget_key` and add `once_per` beside it. Rejected: two claim rows per discretionary push with a cooldown, and FR-006 would have to coordinate them.
- Key loops per drift episode. Rejected by the user (Clarifications Q1, option B): it needs a `drifted_at` stamp that phase 203 owns.

## R4. `push_log` schema after this phase (`zpro006`)

**Decision**: migration `zpro006_push_claims` on the ze-proactive chain (`zpro`, down revision `zpro005`, the next free revision on main):

- delete rows that are not budget claims: `event_type <> 'attention_push' OR idempotency_key IS NULL` (cooldown, conversation, calendar and workflow-failure rows; FR-013);
- drop `ux_push_log_event_idempotency` and `push_log_event_type_sent_at_idx`;
- rename `idempotency_key` to `claim_key` and set it `NOT NULL`;
- add `discretionary BOOLEAN NOT NULL DEFAULT TRUE`, then drop the default (every kept row is a discretionary budget claim);
- add `push_log_claim_key_sent_at_idx (claim_key, sent_at DESC)` and `push_log_discretionary_sent_at_idx (sent_at) WHERE discretionary`.

`event_type` keeps the push kind's event type for new rows; the kept rows say `attention_push`. Downgrade restores the column name, the two old indexes and drops `discretionary`; deleted rows are not restored (dev data is disposable).

**Rationale**: the table becomes one thing, "claims the governor holds". The partial index serves the budget count and the novelty history; the key index serves the cooldown check.

**Alternatives considered**: a new `push_claims` table and dropping `push_log`. Rejected: a rename plus a data copy for no behavioural gain; the name stays private to ze-proactive anyway.

## R5. Novelty history

**Decision**: the bar reads `ProactiveNotifier.recent_discretionary_bodies(hours=48)`, the `payload` of discretionary claims in the window (the push body the notifier stored with the claim; claims exist only for `delivered` and `held`). The bar compares the candidate's push body against them with the E5 embedder and the source's `novelty_similarity_max`. It fetches the history once per `screen()` call and encodes each body once.

Behaviour change: hypotheses are now compared, body against body, with every recent discretionary push (loops, insights, finance, contacts and so on), not only with recently surfaced hypothesis summaries. This is what FR-002 asks for. `PostgresHypothesisStore.list_recently_surfaced_summaries` loses its only caller and is deleted.

**Rationale**: FR-002 forbids a per-source key, and US2 scenario 3 asks for one shared history.

## R6. Surfacing memory (FR-010)

**Decision**: a new ze-priority table `surfacing_memory` (`zpri002_surfacing_memory`, down revision `zpri001`): `id BIGSERIAL`, `kind TEXT CHECK (kind IN ('inline','offer'))`, `source_kind TEXT`, `source_id UUID`, `recorded_at TIMESTAMPTZ DEFAULT now()`, index `(source_kind, source_id, kind, recorded_at DESC)`. `PostgresSurfacingMemory` (`ze_priority/surfacing_memory.py`) has `record(kind, source_kind, source_ids)` and `recorded_within(kind, source_kind, source_id, hours)`. `record` also deletes rows older than 30 days, so the table stays small (the longest window is 7 days).

`TurnSurfacing` takes `memory: SurfacingMemory` as a required argument (today `push_log` is optional and offers are silently off without it). It records inline loop mentions and offers there, and exposes `mentioned_inline_within(source_kind, source_id, hours)`, which the bar reads through the `MentionRecency` protocol.

The windows stay: offers 168 hours (`OFFER_COOLDOWN_HOURS`), inline-then-push `worldstate.push.inline_cooldown_hours` (12), carried on the loop source's `BarThresholds.inline_cooldown_hours`. The hypothesis source sets it to `None`, as today (only loops are recorded).

The table is not a data domain, like `priority_overrides` today. Phase 217 (Data Domain Factory) reviews domains.

**Alternatives considered**: keep the rows in `push_log` under new keys. Rejected by FR-008. Store `last_mentioned_at` on `open_loops`. Rejected: the record belongs to the conversation, not the loop, and 203 owns the loop row.

## R7. Workflow failures (FR-011)

**Decision**: `WorkflowStore.list_failed_executions(since_hours: float) -> list[WorkflowFailure]` reads `workflow_executions` where `status = 'failed'` and `completed_at` is inside the window, newest first, left-joined to `workflows` for the name (`"unknown"` when the run has no workflow). `WorkflowFailure(workflow_id, workflow_name, execution_id, failed_at, error)` goes in `ze_automation/workflow/types.py`. `/status` (`build_status_summary`), `AccountabilityJob` and the morning brief read it. The failure handler stops writing `workflow_failure:<id>`. No migration.

**Rationale**: `finish_execution` stamps `status` and `completed_at` before the handler runs (`scheduler.py:256`), and the runner marks step failures `failed` too, so the run table is already the complete record.

**Behaviour change, intended**: `recover_stale` (`workflow/postgres.py:494-499`) marks runs interrupted by a restart `failed`, and those never reached the failure handler, so the old ledger missed them. They now appear in `/status`, the weekly report and the brief. That is what SC-004 asks ("every failed run"); do not filter them out.

## R8. Calendar reminders (FR-012)

**Decision**: delete the `push_log.log("calendar_reminder:<id>")` write and the `push_log_store` parameter from `CalendarReminderService` and `CalendarPlugin`. Nothing reads the row; `mark_sent`/`mark_unsent` is the idempotency record. No calendar migration.

## R9. Cheap pre-check before expensive jobs

**Decision**: `ProactiveNotifier.on_cooldown(once_per) -> bool` is a read-only check. The goal narrative (model calls per goal), the accountability report and the morning brief call it before building their message and return early with `<job>_skipped_cooldown`. `notify(once_per=...)` repeats the check atomically, so a race between two runs still sends once (spec edge case). `on_cooldown` returns `False` on a store error (fail open, R11).

**Rationale**: without it, moving the cooldown into `notify` would spend model calls on a narrative that is then deduped.

## R10. NLI is explicit (FR-004)

**Decision**: `PushBar.__init__(*, embedder, nli: NLIClient | None, history, mentions)` has no default for `nli`. `None` logs `push_bar_grounding_off` once, at construction. The ze-api wiring always passes `shared.nli_client`; ze-core always builds a `LocalNLIClient` (`ze_core/bootstrap.py:65`), so production never runs without grounding. `embedder` is required and not optional.

**Alternatives considered**: fail startup when NLI is missing. Rejected: tests and the seed CLI build the bar without NLI on purpose; the spec allows either (US2 scenario 4).

## R11. Failure modes

**Decision**: keep today's fail-open rules and name them:

- a claim-store error lets the push go ahead unclaimed and logs `push_claim_failed` (today `attention_claim_failed`);
- a novelty or grounding error passes that condition and logs `push_bar_novelty_check_failed` / `push_bar_grounding_check_failed`;
- a surfacing-memory read error passes `mentioned_recently` and logs `push_bar_mention_check_failed`;
- a `relevance` thunk error is the one fail-closed case: the candidate is rejected as `irrelevant` (`push_bar_relevance_check_failed`). Today such an error escapes and aborts the sweep; rejecting one candidate is narrower.

A failed quiet-hours release keeps the claim (Clarifications Q2): `deliver_held` does not touch claims.

## R12. Bar result and order of conditions

**Decision**: `PushBar.screen(candidates, thresholds) -> list[BarVerdict]`, one per candidate, in input order. Conditions run cheapest first: `low_confidence`, `irrelevant`, `mentioned_recently`, `not_novel`, `ungrounded`. `relevance` and `evidence_labels` are thunks on the candidate, so they are read only when their condition is reached, as `passes_push_bar` does today. Before screening, the job drops candidates whose `once_per` is cooling (`notifier.on_cooldown`), so a loop pushed 2 days ago costs no embedding or NLI each sweep (specs review 2026-10-26, notes 1-2). The first failure names the reason. The job logs `push_bar_rejected` with `source_kind`, `source_id` and `reason` for each rejection. Candidates passing in the same run are not compared with each other (as today).

## R13. Dependency graph changes

- ze-worldstate drops its `ze-correlation` dependency: `surfacing.py` was its only importer of `ze_correlation` (checked with grep on main).
- ze-priority adds `ze-proactive` as a declared dependency (it was transitive); it imports `OncePer`, `is_sent`, `PushCandidate`, `BarThresholds` and `PushOutcome`.
- ze-sdk drops `PushLogStore` and `PushLogEntry` from `ze_sdk.proactive` and adds `OncePer` and `is_sent`.
- ze-core's `proactive.log` data domain moves to ze-proactive (`ze_proactive/data_domain.py`, next to `interruption_data_domains`), so ze-core no longer names `push_log` (SC-001).
- ze-api builds the notifier with `ze_proactive.bootstrap.build_notifier(pool, ...)`, which constructs the `PushLogStore`; `CoreStores.push_log_store`, `ZeContainer._push_log_store` and the `PushLogStore` dependency-map entry go.

## R14. Coordination with other floors

- **200 (Agent Context Derivation, two hunks), 201 (Typed Turn Services), 203 (Open-Loop Lifecycle, one hunk)** and later 207, 210, 211 edit `ze_api/wiring/container.py`. This phase's container edits are small (notifier construction, surfacer, turn surfacing, arbitration sources, the bar). Whichever floor lands second rebases; the `lead` lane owns the file here.
- **203 (Open-Loop Lifecycle)** edits ze-worldstate's lifecycle files, not `surfacing.py` or `bootstrap.py`'s push settings; its only shared file with this phase is `container.py` (above). The loop re-push window needs no loop schema change.
- **213 (One Scheduler)** builds on this phase: after 204, no job reads the push log for its cooldown (213 assumption).
- The `configurable["loop_surfacer"]` key in `ZeContainer` has no reader on main (grep for `"loop_surfacer"` finds only the writer); it goes with the surfacer's new constructor.
