---

description: "Task list for Claim Topology — Shared Confidence, Provenance, and Claim-Kind Vocabulary"
---

# Tasks: Claim Topology — Shared Confidence, Provenance, and Claim-Kind Vocabulary

**Input**: Design documents from `/specs/phases/111-claim-topology/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/claims.md, quickstart.md (all present)

**Tests**: Not explicitly requested in the feature spec, but plan.md's Constitution Check (Principle V) and CLAUDE.md's Test Discipline require unit tests with `AsyncMock`-mocked pools for every new/changed unit; test tasks are included below as mandatory, not optional.

**Organization**: Tasks are grouped by user story (P1 → P2 → P3) per spec.md. Per spec.md's Assumptions "Migration order" note, `Hypothesis`'s decay job (US1) is built first since it fixes a live bug and is independently verifiable; `memory_facts`/`Signal` (US2) follow; `OpenLoop`'s retrofit (also US2) and the staleness extraction (US3) can happen at any point since neither changes anything observable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact — this feature touches six existing packages, no new package

## Path Conventions

Existing monorepo packages (see plan.md's Project Structure) — no new package created:
`core/ze-agents/`, `core/ze-worldstate/`, `core/ze-correlation/`, `core/ze-memory/`,
`core/ze-proactive/`, `core/ze-automation/`, `plugins/ze-calendar/`, `plugins/ze-finance/`,
`plugins/ze-messenger/`, `plugins/ze-news/`

---

## Phase 1: Setup

**Purpose**: Confirm the environment this feature's migrations and tests depend on. No new package, no new dependency (SC-005) — nothing to scaffold.

- [X] T001 Run `make db-up && make migrate` from repo root to confirm the current migration chain (through `zw002`/`zm015`/`zcor001`) applies cleanly before adding `zcor00N`/`zm0NN` on top

**Checkpoint**: Environment ready; no code changes yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared `ze_agents.claims` module every producer retrofit and the decay-fix job import. `Hypothesis` (US1) needs `ClaimKind` and `decay(..., TIME_LINEAR)`; `OpenLoop`/`memory_facts`/`Signal` (US2) need `ClaimKind`/`Provenance`/`decay(..., EVIDENCE_WEIGHTED)`. Nothing in any user story can start before this lands.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Create `core/ze-agents/ze_agents/claims.py` — `ClaimKind` StrEnum (`IDENTITY`, `FACT`, `INFERENCE`, `SUSPICION`, `PRIORITY`), `Provenance` StrEnum closed to exactly `GRAPH_RECALL`/`LIVE_SEARCH`/`PROMPT_SUPPLIED`/`SYNTHESIZED` (FR-002 — never add a plugin/channel member), `DecayProfile` StrEnum (`EVIDENCE_WEIGHTED`, `TIME_LINEAR` — no `FROZEN` profile per FR-005), `Confidence` dataclass (`value: float`, `decay_profile: DecayProfile`), and `decay(value, decay_profile, *, remaining_evidence=None, total_evidence=None, elapsed_days=None) -> float` dispatching on profile — `EVIDENCE_WEIGHTED` branch: floor `0.05`, `max(floor, value * remaining/total)` or floor if `total <= 1` (matches `ze_worldstate/decay.py::cascade_from_evidence`'s existing math exactly, research.md §5); `TIME_LINEAR` branch: `max(0.0, value - 0.03)` per elapsed 30-day period (matches `ze_memory/dream/promoter.py::_run_confidence_decay`'s existing math, research.md §6). Raise a typed `ZeError` subclass (not a bare `ValueError`) when a caller omits the parameters its `decay_profile` requires (contracts/claims.md §1)
- [X] T003 [P] Unit tests for `decay()` in `core/ze-agents/tests/test_claims.py` — `EVIDENCE_WEIGHTED` with `total_evidence <= 1` returns floor `0.05`; `EVIDENCE_WEIGHTED` with remaining evidence returns the weighted-recompute value; `TIME_LINEAR` with `elapsed_days=30` returns `value - 0.03`; `TIME_LINEAR` never returns below `0.0`; calling either profile without its required params raises the typed error, not a bare `ValueError`

**Checkpoint**: `ze_agents.claims` is importable and tested. User story implementation can now begin.

---

## Phase 3: User Story 1 - A correlation's confidence ages like every other claim (Priority: P1) 🎯 MVP

**Goal**: Fix the frozen-hypothesis-confidence bug — `Hypothesis.confidence` currently never changes after creation. Give it a `claim_kind`, retype `EvidenceRef.origin` onto the shared `Provenance` enum, add the backfilled `claim_kind` column, and ship a new scheduled decay job using the shared `TIME_LINEAR` profile.

**Independent Test**: Create a `Hypothesis` with confidence 0.8 dated >30 days in the past, run `HypothesisDecayJob`, and confirm the stored confidence is measurably lower (expect `0.77`) with a `hypothesis_confidence_decayed` log line, and that a hypothesis whose confidence has decayed below the push-bar's `tau_push` threshold is excluded from push eligibility via the existing `passes_confidence` check (quickstart.md §5–6).

### Tests for User Story 1

- [X] T007 [P] [US1] Unit tests for `HypothesisDecayJob` in `core/ze-correlation/tests/test_hypothesis_decay.py` — `AsyncMock`-mocked `PostgresHypothesisStore`: a hypothesis whose decay window has elapsed gets `set_confidence` called with a lower value and the `hypothesis_confidence_decayed` structured log fires; a hypothesis within its window is untouched; confirm the decayed value, once persisted, fails `ze_correlation.push.passes_confidence(confidence, tau_push)` when it crosses the threshold (Acceptance Scenario 2)

### Implementation for User Story 1

- [X] T004 [US1] Add `claim_kind: ClaimKind` field to `Hypothesis` in `core/ze-correlation/ze_correlation/types.py` — value MUST be `INFERENCE` or `SUSPICION` only, never `FACT` (FR-007); change `EvidenceRef.origin` from `Literal["graph_recall", "live_search", "prompt_supplied"]` to `Provenance` (FR-008), which additively gains `SYNTHESIZED`; import `ClaimKind`/`Provenance` from `ze_agents.claims`
- [X] T004B [US1] Populate `claim_kind` at the `Hypothesis(...)` construction call site in `core/ze-correlation/ze_correlation/engine.py` (~line 185) — `claim_kind=ClaimKind.SUSPICION` for every correlation-engine-generated hypothesis, per FR-007's classification rule (spec.md, added post-`/speckit-analyze`); without this the dataclass instantiation raises `TypeError` the first time a new hypothesis is generated, since `claim_kind` has no default. Confirm the `EvidenceRef(...)` construction at the same call site (~line 153, `origin="graph_recall"`) still type-checks against the now-`Provenance`-typed field — no code change expected there, the string literal already matches `Provenance.GRAPH_RECALL`'s value
- [X] T005 [US1] Create migration `core/ze-correlation/ze_correlation/migrations/versions/zcor002_hypothesis_claim_kind.py` (revision `zcor002`, `down_revision = "zcor001"`) — `ALTER TABLE correlation_hypothesis ADD COLUMN claim_kind TEXT`, then `UPDATE correlation_hypothesis SET claim_kind = 'inference' WHERE claim_kind IS NULL` (Assumptions: no corroboration signal exists to distinguish `SUSPICION` on backfill), then `ALTER TABLE correlation_hypothesis ALTER COLUMN claim_kind SET NOT NULL` (FR-016, SC-006); `downgrade()` drops the column
- [X] T006 [US1] In `core/ze-correlation/ze_correlation/store.py`: update `PostgresHypothesisStore.save`/`_row_to_hypothesis` (or equivalent read path) to read/write the new `claim_kind` column and serialize `EvidenceRef.origin` as its `Provenance` string value; add a new `set_confidence(hypothesis_id: UUID, confidence: float) -> None` method mirroring `LoopStore.set_confidence`'s existing shape (contracts/claims.md §6)
- [X] T008 [US1] Create `core/ze-correlation/ze_correlation/jobs/hypothesis_decay.py` — `@proactive_job class HypothesisDecayJob` with `job_id = "hypothesis_decay_sweep"`, constructor takes `hypothesis_store: PostgresHypothesisStore`; `run()` selects hypotheses whose elapsed time since `created_at` (or last decay) has crossed the `TIME_LINEAR` window (mirrors `memory_facts`' 30-day window per the clarification), calls `ze_agents.claims.decay(hypothesis.confidence, DecayProfile.TIME_LINEAR, elapsed_days=...)`, persists via `hypothesis_store.set_confidence(...)`, and logs `hypothesis_confidence_decayed` with the same auditability `OpenLoop`'s `open_loop_confidence_decayed` log already has (contracts/claims.md §6, Acceptance Scenario 1)
- [X] T009 [US1] Register `HypothesisDecayJob` in `core/ze-correlation/ze_correlation/bootstrap.py`'s `register_proactive_jobs` — new standalone `scheduler.add_cron_job(...)` call on its own cadence, alongside (not folded into) the existing `CorrelationJob` registration, matching how `ze-worldstate` registers `StaleSuspicionJob`/`DriftSweepJob`/`PushSweepJob` independently (clarification answer, contracts/claims.md §6)

**Checkpoint**: `Hypothesis` confidence now decays on a schedule; SC-001 verifiable end-to-end per quickstart.md §5–6. This alone is a deployable MVP — the P1 bug fix ships independently of US2/US3.

---

## Phase 4: User Story 2 - Every claim producer speaks one vocabulary for kind and confidence; provenance stays doctrine-scoped (Priority: P2)

**Goal**: Retrofit `OpenLoop`, `memory_facts`, and `Signal` onto the shared `ClaimKind`/`Confidence` vocabulary so a future consumer can compare claims from any producer without a translation layer. `OpenLoop`'s inflow-channel field stops being validated against a closed core whitelist.

**Independent Test**: For each of the four producers, confirm a claim it creates carries a `claim_kind` drawn from the shared enum; for `OpenLoop`, confirm its inflow-channel field accepts an unrecognized plugin string without raising; confirm all pre-existing tests for these producers pass unmodified except where the retrofit specifically changed a type (SC-002, SC-004; quickstart.md §1, §3).

### Tests for User Story 2

- [X] T016 [P] [US2] Add/update tests in `core/ze-worldstate/tests/test_extraction.py` asserting `propose_loop_candidates` no longer raises for a provenance string not in the old 5-value whitelist (e.g. `"a_future_plugins_own_channel"`) — confirms the removed `LoopProvenance(provenance)` coercion (Acceptance Scenario 4, quickstart.md §3); confirm the eleven existing test files using `LoopProvenance.CONVERSATION`/`LoopProvenance.USER_DECLARED` as fixtures still pass unmodified (research.md §3)
- [X] T017 [P] [US2] Add a regression test in `core/ze-worldstate/tests/test_decay.py` confirming `cascade_from_evidence`'s existing assertions (`CONFIDENCE_FLOOR`, `set_confidence.assert_awaited_once_with(...)`) still hold after the internal swap to `ze_agents.claims.decay(...)` (research.md §5) — no new public behavior, only implementation swap
- [X] T018 [P] [US2] Update `core/ze-memory/tests/dream/` promoter tests for the fetch-decay-write shape — confirm `_run_confidence_decay` still produces the same `-0.03`/30-day, `0.50`/`0.25` cliff outcomes per row as the old bulk-SQL version (research.md §6), and add a case asserting the written `claim_kind` matches FR-010's rule (`FACT` for raw/corroborated-synthesized rows, `INFERENCE` for uncorroborated-synthesized rows)
- [X] T019 [P] [US2] Add tests for the four `SignalSource` implementers confirming each emitted `Signal` carries `claim_kind=ClaimKind.FACT` and a `confidence` value distinct from `magnitude`: `plugins/ze-calendar/tests/test_signals.py`, `plugins/ze-messenger/tests/test_signals.py`, `plugins/ze-news/tests/test_signals.py`, `plugins/ze-finance/tests/test_signals.py` (create each file if it doesn't already exist — confirm against each package's existing `tests/` layout first)

### Implementation for User Story 2

- [X] T010 [US2] In `core/ze-worldstate/ze_worldstate/types.py`: replace `class LoopClaimKind(StrEnum): ...` with `from ze_agents.claims import ClaimKind` and `LoopClaimKind = ClaimKind` (FR-006, transparent re-export — zero call-site churn); replace `class LoopProvenance(StrEnum): ...` with a plain (non-`Enum`) class exposing only `CONVERSATION = "conversation"`, `INGESTION = "ingestion"`, `USER_DECLARED = "user_declared"` as string-constant attributes — drop `EMAIL`/`CALENDAR` as declared constants (FR-003; confirmed never pattern-matched outside their own declaration, research.md §3); retype `OpenLoop.provenance` from `LoopProvenance` to `str`
- [X] T011 [US2] In `core/ze-worldstate/ze_worldstate/extraction.py`: remove the `prov = LoopProvenance(provenance)` coercion in `propose_loop_candidates` (which raised `ValueError` for unrecognized strings) and use the incoming `provenance: str` directly; keep the two existing special-case comparisons (`provenance == LoopProvenance.CONVERSATION`, `provenance == LoopProvenance.USER_DECLARED`) unchanged as plain string comparisons (FR-003, contracts/claims.md §3)
- [X] T012 [US2] In `core/ze-worldstate/ze_worldstate/decay.py::cascade_from_evidence`: replace the inline `new_confidence = max(CONFIDENCE_FLOOR, loop.confidence * remaining / total_evidence)` / floor expression with a call to `ze_agents.claims.decay(loop.confidence, DecayProfile.EVIDENCE_WEIGHTED, remaining_evidence=remaining, total_evidence=total_evidence)` (or the `total_evidence <= 1` floor case) — fetching, state-transition, and logging behavior unchanged (FR-006, research.md §5, FR-018)
- [X] T013 [US2] In `core/ze-memory/ze_memory/types.py`: add `claim_kind: ClaimKind` (always `FACT`, FR-012) and `confidence: float` (required, distinct from existing `magnitude`) fields to `Signal`; import `ClaimKind` from `ze_agents.claims`
- [X] T013B [US2] Create migration `core/ze-memory/ze_memory/migrations/versions/zm017_signals_claim_kind.py` (revision `zm017`, `down_revision = "zm016"`) — `Signal`'s two new required fields round-trip through the `memory_signals` table (`zm006`) via `retriever.py::ingest_signal`/`get_signals_by_ids`, which the original plan/data-model missed (added post-`/speckit-analyze`, data-model.md). `ALTER TABLE memory_signals ADD COLUMN claim_kind TEXT`, backfill `UPDATE memory_signals SET claim_kind = 'fact' WHERE claim_kind IS NULL` (every existing signal was perception, per FR-012), `ALTER COLUMN claim_kind SET NOT NULL`; `ADD COLUMN confidence DOUBLE PRECISION`, backfill `UPDATE memory_signals SET confidence = 1.0 WHERE confidence IS NULL`, `ALTER COLUMN confidence SET NOT NULL`; `downgrade()` drops both columns
- [X] T013C [US2] Update `core/ze-memory/ze_memory/retriever.py`: `ingest_signal`'s `INSERT INTO memory_signals` (~line 1233) gains `claim_kind`/`confidence` in its column list, bound to `signal.claim_kind.value`/`signal.confidence`; `get_signals_by_ids`'s `Signal(...)` reconstruction (~line 531) gains `claim_kind=ClaimKind(row["claim_kind"])`/`confidence=row["confidence"]` — without this, retrieval crashes with `TypeError` the moment T013 lands (added post-`/speckit-analyze`)
- [X] T014 [US2] Create migration `core/ze-memory/ze_memory/migrations/versions/zm016_facts_claim_kind.py` (revision `zm016`, `down_revision = "zm015"`) — `ALTER TABLE memory_facts ADD COLUMN claim_kind TEXT`, then backfill per FR-010: `UPDATE memory_facts SET claim_kind = 'fact' WHERE claim_kind IS NULL AND (provenance != 'synthesized' OR corroborated = true)` and `UPDATE memory_facts SET claim_kind = 'inference' WHERE claim_kind IS NULL AND provenance = 'synthesized' AND corroborated = false`, then `ALTER TABLE memory_facts ALTER COLUMN claim_kind SET NOT NULL` (FR-016, SC-006); `downgrade()` drops the column
- [X] T015 [US2] In `core/ze-memory/ze_memory/dream/promoter.py::_run_confidence_decay`: replace the single bulk `UPDATE ... SET confidence = GREATEST(0.0, confidence - 0.03), reviewed = CASE ..., contradicted = CASE ...` statement with a fetch-decay-write loop — `SELECT` eligible rows (`provenance = 'synthesized' AND corroborated = false AND created_at < now() - interval '30 days' AND contradicted = false`), compute each row's new confidence via `ze_agents.claims.decay(confidence, DecayProfile.TIME_LINEAR, elapsed_days=...)`, apply the existing `0.50`/`0.25` `reviewed`/`contradicted` cliff logic in Python, and `UPDATE` each row individually (FR-011, research.md §6 — preserves the exact `-0.03`/30-day rate and cliff thresholds, this is a reimplementation-removal not a behavior change)
- [X] T015B [US2] Populate `claim_kind` on the three `memory_facts` write paths not touched by T015 (added post-`/speckit-analyze` — T014 makes the column `NOT NULL` with no `DEFAULT`, so every INSERT that omits it fails): `core/ze-memory/ze_memory/consolidation_store.py::insert_merged_fact` gains `claim_kind='fact'` in its INSERT (a consolidated/merged fact is corroborated, per FR-010's rule); `core/ze-memory/ze_memory/retriever.py`'s fact-write INSERT (~line 729) gains a `claim_kind` param derived from the `Fact`'s existing `provenance`/`corroborated` fields using FR-010's same raw/synthesized+corroborated rule; `core/ze-memory/ze_memory/dream/promoter.py::_promote`'s own INSERT (~line 186, distinct from `_run_confidence_decay`) gains the literal `claim_kind='inference'` — that statement's other literals (`provenance='synthesized', corroborated=false`) already fix FR-010's rule to `INFERENCE` for this path
- [X] T020 [P] [US2] In `plugins/ze-calendar/ze_calendar/signals.py::CalendarSignalSource.poll`: add `claim_kind=ClaimKind.FACT` and a `confidence=...` value to the `Signal(...)` construction call site (FR-013)
- [X] T021 [P] [US2] In `plugins/ze-messenger/ze_messenger/signals.py`: add `claim_kind=ClaimKind.FACT` and a `confidence=...` value to its `Signal(...)` construction call site (FR-013)
- [X] T022 [P] [US2] In `plugins/ze-news/ze_news/signals.py`: add `claim_kind=ClaimKind.FACT` and a `confidence=...` value to its `Signal(...)` construction call site (FR-013)
- [X] T023 [US2] In `plugins/ze-finance/ze_finance/signals/finance.py::FinanceSignalSource`: this implementer currently builds plain `dict`s in `poll()` rather than constructing `ze_memory.types.Signal` instances directly — update it to construct real `Signal` objects (or the existing conversion path this source's `poll()` result feeds into) so it also carries `claim_kind=ClaimKind.FACT` and a `confidence=...` value like the other three implementers (FR-013); confirm `ze-correlation`/`ze-worldstate` continue polling `signal_sources()` unchanged (FR-014)

**Checkpoint**: All four claim producers speak the shared `ClaimKind`/`Confidence` vocabulary; `Provenance` stays closed to its four doctrine values; `OpenLoop`'s inflow channel is unvalidated. US1 and US2 are both independently functional.

---

## Phase 5: User Story 3 - Staleness checks stop being reinvented per mechanism (Priority: P3)

**Goal**: Extract the duplicated "cutoff = now − window; past it → stale" shape from three sweep jobs into one shared helper in `core/ze-proactive`, without changing any job's state-transition or window-configuration logic.

**Independent Test**: Confirm `stale_suspicion.py`, `drift_sweep.py` (via `list_drift_candidates`), and `stuck_goals.py` (via `list_stuck`) produce identical stale/not-stale decisions before and after the extraction, for the same inputs (SC-003, quickstart.md §2).

### Tests for User Story 3

- [X] T025 [P] [US3] Unit tests for `is_stale()` in `core/ze-proactive/tests/test_staleness.py` — a timestamp older than the window returns `True`; a timestamp within the window returns `False`; a timestamp exactly at the cutoff returns `True` (`<=`, per data-model.md); confirm the optional `now` override is honored for deterministic testing

### Implementation for User Story 3

- [X] T024 [US3] Create `core/ze-proactive/ze_proactive/staleness.py` — pure function `is_stale(timestamp: datetime, window_days: int, *, now: datetime | None = None) -> bool`, computing `cutoff = (now or datetime.now(UTC)) - timedelta(days=window_days); return timestamp <= cutoff` (FR-015, mirrors `stale_suspicion.py`'s existing inline shape exactly)
- [X] T026 [US3] Update `core/ze-worldstate/ze_worldstate/jobs/stale_suspicion.py` to call `ze_proactive.staleness.is_stale(loop.created_at, self._window_days)` in place of its inline `cutoff = datetime.now(timezone.utc) - timedelta(days=self._window_days)` / `loop.created_at <= cutoff` computation — state-transition logic (`transition(..., LoopState.DROPPED.value)`) unchanged
- [X] T027 [US3] In `core/ze-worldstate/ze_worldstate/store.py::PostgresLoopStore.list_drift_candidates`: drop the SQL-side `drift_deadline <= now()` predicate (keep the `state = $1 AND drift_deadline IS NOT NULL` filter), returning all state-eligible candidates with a set deadline; update `core/ze-worldstate/ze_worldstate/jobs/drift_sweep.py::DriftSweepJob.run` to call `ze_proactive.staleness.is_stale(loop.drift_deadline, ...)` per candidate before applying `drift.is_drift_eligible(loop)` (research.md §7 — safe at single-user scale)
- [X] T028 [US3] In `core/ze-automation/ze_automation/goals/postgres.py::PostgresGoalStore.list_stuck`: drop the `idle_days` cutoff from the SQL `HAVING` clause while keeping the separate `alert_cooldown_days` re-alert-suppression predicate in SQL (unrelated to FR-015, research.md §7); update `core/ze-automation/ze_automation/jobs/stuck_goals.py::StuckGoalJob.run` (or wherever the idle-days decision is now made) to call `ze_proactive.staleness.is_stale(...)` per candidate for the idle-days check

**Checkpoint**: All three sweep jobs share one staleness-cutoff implementation (SC-003); each job's own state-transition and window-configuration logic is unchanged (FR-015).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide verification that spans all three user stories.

- [ ] T029 [P] Run `make lint` across all six touched packages and fix any violations
- [ ] T030 [P] Run `make test-worldstate && make test-correlation && make test-memory && make test-plugin && make test-proactive && make test-automation` and confirm every pre-existing test passes unmodified except tests specifically updated in T016–T019/T025 (SC-004, quickstart.md §4)
- [ ] T032B [P] Verify SC-005 (added post-`/speckit-analyze` — the only Success Criterion with no prior verification task) — `git diff --stat main -- '**/pyproject.toml'` on this feature's branch should show zero changed lines, confirming no package touched by this feature gained a new `[project.dependencies]` entry; all four producer packages already depend on `ze-agents` per research.md §9
- [ ] T031 Run the quickstart.md §1 grep checks — exactly one `class ClaimKind`/`class Provenance` definition (`core/ze-agents/ze_agents/claims.py`), zero `class LoopClaimKind` hits in `ze-worldstate`, zero `EMAIL`/`CALENDAR` hits in `ze_worldstate/types.py`, `LoopProvenance` is a plain class not a `StrEnum` (SC-002)
- [ ] T032 Run the quickstart.md §2 grep check — exactly one inline `cutoff = now - timedelta(...)`-shaped computation across the repo, inside `core/ze-proactive/ze_proactive/staleness.py`, with none of the three sweep call sites computing a stale cutoff inline anymore (SC-003)
- [ ] T033 Run the quickstart.md §5–7 live-DB validation against a migrated dev database — create a backdated `Hypothesis`, run `HypothesisDecayJob`, confirm `confidence` drops from `0.8` to `0.77` with the `hypothesis_confidence_decayed` log line (SC-001), confirm zero `NULL` `claim_kind` rows in `correlation_hypothesis`/`memory_facts` post-migration (SC-006)
- [ ] T034 Update `specs/phases/111-claim-topology/spec.md`'s `**Status**: Draft` line to `Implemented` in the same commit as the final implementation task, per this repo's Spec Status Audit convention

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (both US1 and US2 import `ze_agents.claims`)
- **User Story 1 (Phase 3)**: Depends on Foundational only. No dependency on US2 or US3
- **User Story 2 (Phase 4)**: Depends on Foundational only. Independent of US1 — can run in parallel with it (different packages/files) despite being sequenced second per the spec's Assumptions
- **User Story 3 (Phase 5)**: Depends on Foundational only (in practice, not even on `ze_agents.claims` — it only needs `core/ze-proactive`). Fully independent of US1 and US2; can run at any point, including in parallel with both
- **Polish (Phase 6)**: Depends on all three user stories being complete

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3. Ships alone as a deployable MVP (the frozen-confidence bug fix)
- **US2 (P2)**: No dependency on US1/US3. Touches `ze-worldstate`, `ze-memory`, and four plugin packages — none of which US1 touches
- **US3 (P3)**: No dependency on US1/US2. Touches `ze-proactive`, `ze-worldstate/jobs/`, `ze-automation` — the `ze-worldstate/jobs/` overlap with US2's `decay.py`/`extraction.py` changes is in different files within the same package, so still parallel-safe

### Within Each User Story

- Migrations (T005, T014, T013B) before store/read-write changes that depend on the new column(s) (T006, T013C) — T014 before T015/T015B (promoter and the other two write paths read the column T014 adds); T013B before T013C (ingest/read code needs the columns to exist)
- Type changes (T004, T010, T013) before the store/job/call-site code that constructs instances of the changed type — T004 before T004B (engine.py's `Hypothesis(...)` call needs the field to exist before it can pass it); T013 before T013C
- Tests (T007, T016–T019, T025) can be written in parallel with implementation since `AsyncMock` fixtures don't require the implementation to exist first, but per CLAUDE.md Test Discipline should be run against the finished implementation before considering a task done

### Parallel Opportunities

- T003 (Foundational tests) can run alongside T002 is *not* safe — same file dependency (tests import from the module T002 creates) — write T002 first, T003 can be authored in parallel but not run until T002 lands
- Within US2, T020/T021/T022 (calendar/messenger/news signal call sites) are fully parallel — three different plugin packages, no shared file
- T016/T017/T018/T019 (US2 test tasks) are parallel — four different test files/packages
- US1 (Phase 3) and US2 (Phase 4) can be staffed in parallel once Phase 2 completes, despite the sequential P1→P2 numbering
- US3 (Phase 5) can be staffed in parallel with either US1 or US2

---

## Parallel Example: User Story 2 signal call sites

```bash
# Launch all four SignalSource retrofits together once T013 (Signal type change) lands:
Task: "Add claim_kind/confidence to Signal(...) call in plugins/ze-calendar/ze_calendar/signals.py"
Task: "Add claim_kind/confidence to Signal(...) call in plugins/ze-messenger/ze_messenger/signals.py"
Task: "Add claim_kind/confidence to Signal(...) call in plugins/ze-news/ze_news/signals.py"
Task: "Convert FinanceSignalSource's dict-based poll() to real Signal(...) construction with claim_kind/confidence in plugins/ze-finance/ze_finance/signals/finance.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (`ze_agents.claims` — CRITICAL, blocks everything)
3. Complete Phase 3: User Story 1 (Hypothesis decay job — fixes the live bug)
4. **STOP and VALIDATE**: Run quickstart.md §5–6 against a migrated dev DB
5. Deploy/demo if ready — the P1 bug fix is independently shippable

### Incremental Delivery

1. Setup + Foundational → shared vocabulary ready
2. Add US1 → validate independently → deploy (MVP: the frozen-confidence bug is fixed)
3. Add US2 → validate independently → deploy (all four producers now share one vocabulary)
4. Add US3 → validate independently → deploy (staleness duplication removed)
5. Phase 6 Polish → full quickstart.md pass, spec status flip to `Implemented`

### Parallel Team Strategy

With multiple developers, after Phase 2 (Foundational) completes:

- Developer A: User Story 1 (`core/ze-correlation`)
- Developer B: User Story 2 (`core/ze-worldstate`, `core/ze-memory`, plugin signal sources)
- Developer C: User Story 3 (`core/ze-proactive`, sweep job call sites)

All three integrate independently — no shared files across stories except `core/ze-worldstate/ze_worldstate/jobs/` (US2 touches `decay.py`/`extraction.py`, US3 touches `stale_suspicion.py`/`drift_sweep.py` — different files, safe).

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Task IDs are grouped by phase for readability (Foundational: T002–T003; US1 impl: T004, T004B, T005–T006, T008–T009; US1 tests: T007; US2 impl: T010–T015, T015B, T013B–T013C, T020–T023; US2 tests: T016–T019; US3 impl: T024, T026–T028; US3 tests: T025; Polish: T029–T034, T032B) — execute in the Dependencies & Execution Order above, not strictly numeric order, since tests and implementation within a story interleave; lettered IDs (T004B, T013B, T013C, T015B, T032B) were added during `/speckit-analyze` remediation and sit logically beside their base-numbered task rather than at the end of the file
- Per FR-017, no task here introduces a `Contribution` type or an arbitration mechanism — those remain out of scope, covered by a later feature
- Per FR-018, no task changes surfacing/push-gating/inline-mention behavior for `OpenLoop`, `Signal`, or `memory_facts` — only `Hypothesis` (US1) gains an observable behavior change
- Commit after each task or logical group; verify tests fail before implementing where a test task precedes its implementation task

