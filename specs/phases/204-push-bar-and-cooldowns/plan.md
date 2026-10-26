# Implementation Plan: Push Bar and Cooldowns

**Branch**: `204-push-bar-and-cooldowns` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/204-push-bar-and-cooldowns/spec.md` (clarified 2026-10-26)

## Summary

One push bar, one claim rule, and every record back with its owner.

- **Push bar** (`ze_priority/push_bar.py`): one `PushBar` built at startup with the embedder, NLI (explicit; `None` logs "grounding off" once), the governor's push history and `TurnSurfacing`'s mention record. `AttentionArbitrationJob` screens each source's candidates through it. Loops and hypotheses become candidate sources: they build `PushCandidate` values and send the one the job picks. A new source is an adapter only (SC-005).
- **One claim rule** (`ze-proactive`): `notify(..., once_per=OncePer(key, within))`. The check, the record and the discretionary budget claim run in one transaction under advisory locks. Only `delivered` and `held` keep the claim. `once_per` absorbs `budget_key` (no window = once ever, today's rule) and `dedup_hours`; `duplicate` becomes `deduped`. A drifting loop is pushed at most once per 7 days (Clarifications Q1).
- **Records with their owners**: `push_log` holds only the governor's claims (`zpro006`) and is private to ze-proactive. Inline-mention and offer cooldowns move to a ze-priority table owned by `TurnSurfacing` (`zpri002`). Workflow failures are read from `workflow_executions`. The calendar's write-only push-log row goes.
- **Cooldown jobs** (accountability, goal narrative, morning brief, workflow-failure alert) use `once_per`; the three expensive ones pre-check `on_cooldown` before building. Five hand-rolled outcome checks use `is_sent`.

Research: [research.md](research.md). Data: [data-model.md](data-model.md). Contracts: [contracts/](contracts/). Verification: [quickstart.md](quickstart.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: asyncpg, Alembic (raw SQL), the local E5 embedder and NLI cross-encoder (already built by ze-core). No new library.

**Storage**: PostgreSQL. `push_log` restructured (`zpro006`, ze-proactive chain); new `surfacing_memory` (`zpri002`, ze-priority chain); `workflow_executions` read only.

**Testing**: pytest (`asyncio_mode=auto`), test-pg (`make test-pg`, `apps/ze-api/tests/pg/`) for the claim transaction, the migration, the surfacing table and the failure query.

**Target Platform**: Ze running locally (self-hosted)

**Project Type**: monorepo (core packages, plugins, ze-api). No web, REST or WS change.

**Performance Goals**: none new. The bar encodes each history body once per arbitration run instead of once per candidate.

**Constraints**: pre-v1 hard cuts; plugins import `OncePer`/`is_sent` from `ze_sdk.proactive`; ze-worldstate and ze-correlation must not import ze-priority (research R1).

**Scale/Scope**: about 35 source files in 11 packages, 2 migrations, about 30 test files, 16 public docs.

## Blast radius (`graphify affected --depth 2`, graph rebuilt on the floor 2026-10-26)

| Symbol | Source callers, by package | Test modules |
|---|---|---|
| `PushLogStore` | ze-api: `wiring/container.py`, `wiring/stores.py`, `api/ws/commands.py` (via `/status`); ze-automation: `bootstrap.py`, `jobs/accountability.py`, `jobs/goal_narrative.py`, `rest.py`; ze-proactive: `notifier.py`; ze-calendar: `plugin.py`; ze-personal: `plugin.py`. Grep adds: ze-api `wiring/agents.py`, `wiring/jobs.py`; ze-core `bootstrap.py` (data domain); ze-sdk `proactive.py`; ze-personal `jobs/briefing.py`; ze-calendar `reminders/calendar.py`; ze-priority `turn.py`; ze-worldstate `surfacing.py`, `bootstrap.py` | 14: pg `test_acceptance`, `test_loop_confirmation_pg`, `test_push_log_window_pg`; ze-proactive `test_push_log_store`; ze-calendar `test_reminders`; ze-api `test_workspace_followthrough`, `test_accountability_contract`, `test_quiet_hours_routes`, `test_container_config`, `test_container_script_runner`, `test_container_tier_judge`, `agents/test_bootstrap`; ze-automation `test_accountability`, `test_goal_narrative` |
| `passes_novelty`, `passes_grounding` | ze-correlation `push.py`; ze-worldstate `surfacing.py` | ze-correlation `test_push.py` |
| `ProactiveNotifier` | ze-api `wiring/container.py`, `api/ws/held.py`; ze-automation `agents/goals/agent.py`, `bootstrap.py`, `holds/resumer.py`, `jobs/{accountability,cost_anomaly,goal_narrative,goal_suggestion,stuck_goals}.py`; ze-correlation `bootstrap.py`; ze-proactive `jobs/release_held.py`; ze-calendar, ze-finance, ze-messenger, ze-personal `plugin.py`; ze-finance `jobs/recurring.py`; ze-messenger `inbound/processor.py` | 9, including `test_notifier`, `test_governor_acceptance`, `test_briefing`, `test_insights`, `test_reminders`, `test_native` |
| `LoopSurfacer` / `build_loop_surfacer` | ze-worldstate `bootstrap.py`; ze-api `wiring/container.py` (`hooks.py`, `lifespan.py` and `cli/seed.py` reach it only through `build_container`) | ze-worldstate `test_surfacing`, `test_bootstrap`; ze-priority `test_arbitration`; ze-api `test_shipped_config_keys`; pg `test_acceptance`, `test_loop_evidence` |
| `CorrelationPushCandidateSource` | ze-correlation `bootstrap.py` | ze-correlation `test_push.py` |
| `TurnSurfacing` | ze-api `wiring/container.py` (`lifespan.py`, `cli/seed.py` through `build_container`) | ze-priority `test_turn`; pg `test_loop_confirmation_pg`; 6 ze-api container tests |
| `AttentionArbitrationJob` | ze-api `wiring/jobs.py`, `wiring/container.py` | ze-priority `test_arbitration` |
| `make_workflow_failure_handler` | ze-automation `bootstrap.py`; ze-api `wiring/container.py` | ze-automation `test_failure_handler`, `test_configure_executor`; ze-calendar `test_reminders` (a local copy of the handler, deleted) |
| `build_status_summary` | ze-api `api/ws/commands.py`, `api/ws/endpoint.py` | ze-api `test_ws_cancel_thread`, `test_ws_commands_reset_removed` |
| `CalendarReminderService` | ze-calendar `jobs/calendar_reminder.py`, `plugin.py` | ze-calendar `test_reminders`, `test_api_routes` |
| `notify(budget_key=…)` (grep) | 12 call sites, listed in [contracts/notifier.md](contracts/notifier.md) | ze-proactive `test_notifier`, ze-api `test_governor_acceptance`, ze-priority `test_arbitration`, ze-automation `test_create_goal_convergence`, `test_executor_reuse_notice`, ze-correlation `test_push`, ze-worldstate `test_surfacing`, ze-finance `test_recurring_job`, ze-messenger `test_inbound_relay_push`, ze-personal `test_insights` |
| `exists_recent`, `list_recently_surfaced_summaries` | no caller outside the deleted code | ze-proactive `test_notification_store` |

## Constitution Check

*GATE: passed before Phase 0 and re-checked after Phase 1.*

- **I. Spec-First Development**: PASS. Spec clarified 2026-10-26 (two user answers); plan, research, data model, contracts and quickstart exist before code. Status moves to Implemented in the commit that finishes the phase.
- **II. Single-User Model**: PASS. No user scoping; serialising discretionary claims with one advisory lock relies on one user.
- **III. Layered Package Architecture**: PASS. The bar lives in ze-priority, above both sources; candidate types live in ze-proactive, below them. ze-worldstate loses its ze-correlation edge; ze-priority declares its existing ze-proactive edge. Plugins import through `ze_sdk.proactive`. No upward import.
- **IV. Typed, Explicit Python**: PASS. Dataclasses for `OncePer`, `PushCandidate`, `BarThresholds`, `BarVerdict`, `ClaimResult`, `WorkflowFailure`; Protocols for `PushHistory`, `MentionRecency`, `SurfacingMemory`, the source; `PushPolicyError` for misuse.
- **V. Test Discipline**: PASS. Each story starts with a failing test through its real interface (`notify`, `AttentionArbitrationJob.run`, `/status`, `TurnSurfacing`); SQL is tested on test-pg; no real model call.
- **VI. Explicit Persistence**: PASS. Two raw-SQL migrations on their owners' chains (`zpro006`, `zpri002`).
- **VII. One LLM Gateway, Local Embeddings**: PASS. Novelty uses the local E5 embedder, grounding the local NLI; no model call added.
- **VIII. Pre-v1 Hard Cuts**: PASS. `budget_key`, `dedup_hours`, `duplicate`, the push-log helpers, the free bar functions and `list_recently_surfaced_summaries` are deleted, not wrapped; non-claim rows are deleted by migration.

## Project Structure

### Documentation (this feature)

```text
specs/phases/204-push-bar-and-cooldowns/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── notifier.md
│   ├── push-bar.md
│   └── migrations-and-failures.md
├── checklists/
└── tasks.md
```

### Source Code (repository root)

```text
core/contracts/ze-proactive/ze_proactive/{types,candidates,push_log_store,notifier,attention_budget,bootstrap,data_domain,notification_store}.py
core/contracts/ze-proactive/ze_proactive/migrations/versions/zpro006_push_claims.py
core/arbitration/ze-priority/ze_priority/{push_bar,arbitration,turn,surfacing_memory}.py
core/arbitration/ze-priority/ze_priority/migrations/versions/zpri002_surfacing_memory.py
core/cognition/ze-worldstate/ze_worldstate/{surfacing,bootstrap}.py
core/cognition/ze-correlation/ze_correlation/{push,bootstrap,store}.py
core/automation/ze-automation/ze_automation/{bootstrap,rest}.py
core/automation/ze-automation/ze_automation/jobs/{accountability,goal_narrative,stuck_goals,goal_suggestion}.py
core/automation/ze-automation/ze_automation/goals/{proposal,executor}.py
core/automation/ze-automation/ze_automation/workflow/{types,store,postgres}.py
core/engine/ze-core/ze_core/bootstrap.py                       # drop the proactive.log domain line
packages/ze-sdk/ze_sdk/proactive.py
plugins/ze-personal/ze_personal/{plugin.py,jobs/briefing.py,jobs/insights.py,jobs/contacts.py}
plugins/ze-calendar/ze_calendar/{plugin.py,reminders/calendar.py}
plugins/ze-finance/ze_finance/jobs/recurring.py
plugins/ze-messenger/ze_messenger/inbound/processor.py
apps/ze-api/ze_api/wiring/{container,stores,agents,jobs}.py
apps/ze-api/config/config.yaml                                 # worldstate.push.repush_after_days: 7
```

**Structure Decision**: each record moves to the package that owns its meaning (research R1, R2, R6, R7). The only new modules are `ze_proactive/candidates.py`, `ze_priority/push_bar.py` and `ze_priority/surfacing_memory.py`.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first, T001–T005): the ze-proactive public surface every lane builds against, with tests: `OncePer`, `is_sent`, the new `PushOutcome` (`types.py`); `PushCandidate`, `BarThresholds` (`candidates.py`); `ProactiveNotifier.notify(once_per=…)`, `on_cooldown`, `recent_discretionary_bodies` with `budget_key`/`dedup_hours` removed; the `ze_sdk.proactive` exports. `InMemoryPushLog` (`ze_proactive/testing.py`) lets lanes test with a real notifier. The claim store and `zpro006` (T006–T010) follow in `lead` while the other lanes work: they test against fakes of the notifier and need only the signatures. Record the two revisions (`zpro006`, `zpri002`) in the "204 Handoffs" note.

| Lane | Model / role | Owns (files and dirs, disjoint) | Tasks | Starts after | Reviewer |
|------|--------------|---------------------------------|-------|--------------|----------|
| lead | Sonnet ENG lead | `core/contracts/ze-proactive/ze_proactive/` (all, incl. `testing.py` and `migrations/`), `core/contracts/ze-proactive/tests/`; `packages/ze-sdk/ze_sdk/proactive.py`, `packages/ze-sdk/tests/`; `core/engine/ze-core/ze_core/bootstrap.py` (the `proactive.log` line only); `apps/ze-api/ze_api/wiring/{container,stores,agents,jobs}.py`; `apps/ze-api/tests/pg/{conftest.py,test_harness_smoke.py,test_push_claims_pg.py}` (and deleting `test_push_log_window_pg.py`), `apps/ze-api/tests/test_governor_acceptance.py`, `apps/ze-api/tests/test_container_*.py`, `apps/ze-api/tests/api/{test_workspace_followthrough,test_accountability_contract,test_quiet_hours_routes}.py`, `apps/ze-api/tests/agents/test_bootstrap.py`; merges; final gates | T001–T010, T036–T041 | - | floor reviewer (Maestro assigns) |
| bar | Sonnet ENG | `core/arbitration/ze-priority/ze_priority/{push_bar,arbitration}.py`, `core/arbitration/ze-priority/pyproject.toml`, `core/arbitration/ze-priority/tests/{test_push_bar,test_arbitration}.py`; `core/cognition/ze-worldstate/ze_worldstate/{surfacing,bootstrap}.py`, `core/cognition/ze-worldstate/pyproject.toml`, `core/cognition/ze-worldstate/tests/{test_surfacing,test_bootstrap}.py`; `core/cognition/ze-correlation/ze_correlation/{push,bootstrap,store}.py`, `core/cognition/ze-correlation/tests/{test_push,test_hypothesis_decay}.py`; `uv.lock`; `apps/ze-api/config/config.yaml`, `apps/ze-api/tests/test_shipped_config_keys.py`; `apps/ze-api/tests/pg/{test_acceptance,test_loop_evidence}.py` | T021–T027, T031 | contract step | floor reviewer (Maestro assigns) |
| conv | Sonnet ENG | `core/arbitration/ze-priority/ze_priority/{turn,surfacing_memory}.py`, `core/arbitration/ze-priority/ze_priority/migrations/versions/zpri002_surfacing_memory.py`, `core/arbitration/ze-priority/tests/test_turn.py`, `apps/ze-api/tests/pg/{test_surfacing_memory_pg,test_loop_confirmation_pg}.py` | T032–T035 | contract step | floor reviewer (Maestro assigns) |
| jobs | Sonnet ENG | `core/automation/ze-automation/ze_automation/{bootstrap,rest}.py`, `.../jobs/{accountability,goal_narrative,stuck_goals,goal_suggestion}.py`, `.../goals/{proposal,executor}.py`, `.../workflow/{types,store,postgres}.py`, `core/automation/ze-automation/tests/` (all); `plugins/ze-personal/ze_personal/{plugin.py,jobs/briefing.py}`, `plugins/ze-personal/tests/jobs/test_briefing.py`; `apps/ze-api/tests/test_cooldown_jobs.py` (new), `apps/ze-api/tests/pg/test_workflow_failures_pg.py` (new) | T011–T016, T028–T030 | contract step | floor reviewer (Maestro assigns) |
| jr1 | Haiku JR | `plugins/ze-finance/ze_finance/jobs/recurring.py`, `plugins/ze-finance/tests/test_recurring_job.py`; `plugins/ze-messenger/ze_messenger/inbound/processor.py`, `plugins/ze-messenger/tests/test_inbound_relay_push.py`; `plugins/ze-personal/ze_personal/jobs/{insights,contacts}.py`, `plugins/ze-personal/tests/jobs/test_insights.py`, `plugins/ze-personal/tests/jobs/test_contact_review.py`; `plugins/ze-calendar/ze_calendar/{plugin.py,reminders/calendar.py}`, `plugins/ze-calendar/tests/jobs/test_reminders.py` | T017–T020 | contract step | floor reviewer (Maestro assigns) |
| docs | Haiku DOCS | `docs/{architecture,cognitive-architecture,configuration,extending-ze,memory,native-interface,package-architecture,scheduled-jobs,sdk,workflows}.md`, `core/arbitration/ze-priority/README.md`, `core/cognition/ze-worldstate/README.md`, `core/cognition/ze-correlation/README.md`, `core/contracts/ze-proactive/README.md`, `core/automation/ze-automation/README.md`, `packages/ze-sdk/README.md`, `AGENTS.md`, `specs/README.md` (204 Status cell), `specs/phases/204-push-bar-and-cooldowns/spec.md` (Status line), `specs/arch/attention-arbitration.md` | T042–T045 | all code lanes merged | floor reviewer (Maestro assigns) |

**Rules**:

- **One lane per file.** `ze_priority/` is split by file between `bar` (`push_bar.py`, `arbitration.py`, `pyproject.toml`) and `conv` (`turn.py`, `surfacing_memory.py`, `migrations/`). `ze-personal` is split the same way: `jobs` owns `plugin.py` and `briefing.py`; `jr1` owns `insights.py` and `contacts.py`.
- **Shared files belong to `lead`**: the ze-api wiring and the ze-api tests outside the lanes' own new files. Lanes do not edit them; `lead` wires the new constructors from the contracts after merging the lanes (T037–T038).
- **`bar` and `conv` meet at one Protocol.** `bar` defines `MentionRecency` in `push_bar.py` and tests the bar with a fake; `conv` adds `TurnSurfacing.mentioned_inline_within` with that exact signature ([contracts/push-bar.md](contracts/push-bar.md)).
- **The FR-007 parametrized test lives in ze-api** (`apps/ze-api/tests/test_cooldown_jobs.py`, lane `jobs`): the morning brief is in ze-personal, which ze-automation tests may not import.
- **Branches.** Each lane works on a sub-branch of the floor branch. `lead` merges `jr1` → `conv` → `jobs` → `bar` (T036), wires (T037–T038), then runs the gates (T039–T041). Each lane is reviewed as it finishes.
- **Between the contract step and the merge**, call sites a lane does not own may fail with the new `notify` signature. Each lane runs only its own package suites; `lead` runs `make test-py` after the last merge.
- **`jr1` is Haiku** because each task names the file, the exact replacement and the test to change (mechanical `budget_key=` → `once_per=OncePer(...)`, `is_sent`, and two deletions in the calendar).
- **`docs` runs last**, from the finished diff.
- **Cross-floor** (research R14): `ze_api/wiring/container.py` is also edited by floors 200, 201 and 203 (and later 207, 210, 211). Whichever floor lands second rebases; keep this phase's container hunks small. 203 also edits `ze_worldstate/bootstrap.py` and `container.py` in hunks disjoint from this phase's (research R14). 213 starts after this phase lands.

## Complexity Tracking

None.
