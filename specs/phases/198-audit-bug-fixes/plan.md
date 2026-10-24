# Implementation Plan: Audit Bug Fixes

**Branch**: `198-audit-bug-fixes` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/198-audit-bug-fixes/spec.md`

## Summary

Eleven small behaviour fixes: ten from the 2026-10-22 architecture review, plus B15, which the user added on 2026-10-22. Each one starts with a failing test through the real interface, then gets the smallest change that makes it pass. No migration, no new module that a later phase must delete (except the B2 key-diff guard and the B15 abort registration, which phase 201 replaces, and the B9 call, which phase 207 replaces), no REST or WS shape change. The decisions behind each fix are in [research.md](research.md); how to see each fix working is in [quickstart.md](quickstart.md). There is no new data model and no new contract, so this phase has no `data-model.md` and no `contracts/`.

| Bug | Fix in one line | Owning package(s) |
|---|---|---|
| B1 | `ZeApiSettings.timezone`; copy `timezone` into subtask, compound and delegate contexts; inject it into `GoalExecutor` | ze-api, ze-core, ze-agents, ze-automation |
| B2 | `ZeContainer._build_config` sets `turn_extractor`; a test diffs the two key sets | ze-api |
| B4 | `LoopSurfacer` takes NLI in its constructor; the governor's claim stores the body; loop novelty reads `attention_push` | ze-worldstate, ze-proactive, ze-api wiring |
| B5 | `PriorityView` owns the override store and returns the user's order; `computed_rank` kept for collisions; arbitration orders by it and skips pushed-down items | ze-priority, ze-api wiring |
| B6 | A non-compacting trim keeps the leading summary (Q5); the compaction readout is derived from the summary message the turn's history opens with; `compaction_span` state is cut | ze-core |
| B9 | The follow-up turn starter calls `send_confirmation_request` on an interrupted outcome | ze-api |
| B10 | The reducer's `paused` event sets attention for a non-open thread; `ConfirmationFrameHandler` stops writing WS flags | ze-web |
| B11 | Four jobs write their cooldown only after `delivered` or `held`; the workflow-failure alert cooldown gets its own key; a failed calendar reminder is un-marked | ze-personal, ze-automation, ze-calendar |
| B13 | Remove `automation.goals` and `automation.workflows` from `automation_data_domains` | ze-automation |
| B14 | `goals/lifecycle.py` preconditions used by the tools and the WS screen actions | ze-automation, ze-api |
| B15 | `invoke_raw_turn` and `resume_turn` create an `AbortToken`, register it in the container's `_abort_tokens` for the turn, and pass it in the config | ze-core |

## Technical Context

**Language/Version**: Python 3.12 (uv workspace); TypeScript 5 (ze-web, Vite, vitest)

**Primary Dependencies**: LangGraph, FastAPI, asyncpg, structlog; React, zustand

**Storage**: PostgreSQL. No schema change. `push_log.payload` for `attention_push` rows changes meaning from title to body (no reader today).

**Testing**: pytest (`asyncio_mode = "auto"`, `AsyncMock` pools, no real LLM); vitest for ze-web. Graph-level test with `MemorySaver` for B6.

**Target Platform**: local self-hosted server + browser

**Project Type**: web service + SPA (monorepo)

**Performance Goals**: no new hot-path work except one extra override read per `PriorityView.rank()` call (it was already done by REST and `TurnSurfacing`) and one per arbitration run.

**Constraints**: phase 199 (floor "199 Claim Honesty Fixes", agent Ledger) edits `ze_core/orchestration/nodes/memory.py` lines 199-223 in parallel. 198 edits only that file's compaction lines (252-342).

**Scale/Scope**: about 30 source files across 9 packages, plus tests. No migration.

## Constitution Check

*Source: `.specify/memory/constitution.md`.*

- **I. Spec-First Development** — PASS. Spec, plan and tasks in `specs/phases/198-audit-bug-fixes/`.
- **II. Single-User Model** — PASS. No user scoping added.
- **III. Layered Package Architecture** — PASS. ze-personal reads `PriorityView` from ze-priority (declared dependency, `plugins/ze-personal/pyproject.toml:14`). ze-calendar changes stay in the plugin. `goal_actions.py` (ze-api) imports the new rules from `ze_automation.goals`, a declared dependency. No plugin imports `ze_core`.
- **IV. Typed, Explicit Python** — PASS. Constructor injection for the NLI client, override store and timezone. Refused goal transitions return the tool's existing `{"error": ...}` shape; no bare exceptions.
- **V. Test Discipline** — PASS. Each fix starts with a failing test through its real interface (FR-025).
- **VI. Explicit Persistence** — PASS. No schema change.
- **VII. One LLM Gateway, Local Embeddings** — PASS. No new model call.
- **VIII. Pre-v1 Hard Cuts** — PASS. Removed, not wrapped: the `nli_client` call parameter on `LoopSurfacer`, the `worldstate_loop_push` key, the merge calls in REST and `TurnSurfacing`, `TurnSurfacing`'s override-store dependency, the `compaction_span` state field, the duplicate data domains. The two stopgaps (B2 guard, B9 call) are in-tree fixes that phases 201 and 207 replace; they are not compatibility shims.

## Project Structure

### Documentation (this feature)

```text
specs/phases/198-audit-bug-fixes/
├── spec.md
├── plan.md              # this file
├── research.md          # decisions per bug
├── quickstart.md        # how to see each fix
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (files this phase touches)

```text
apps/ze-api/ze_api/
├── settings.py                         # B1: ZeApiSettings.timezone
├── wiring/container.py                 # B2 turn_extractor; B9 follow-up confirmation; B4/B5 wiring
└── api/ws/goal_actions.py              # B14: shared rules
apps/ze-api/tests/
├── test_settings_timezone.py           # new (B1)
├── test_container_config.py            # new (B2)
├── test_data_domains_unique.py         # new (B13)
└── api/{test_workspace_followthrough.py, test_goal_actions.py}

core/engine/ze-core/ze_core/
├── orchestration/nodes/execution.py    # B1
├── orchestration/nodes/memory.py       # B6 (compaction lines only): keep the summary, stamp its span
├── orchestration/nodes/trace.py        # B6
├── orchestration/state.py              # B6: drop compaction_span
└── conversation/turn.py                # B15: abort token per turn
core/contracts/ze-agents/ze_agents/delegate.py   # B1
core/contracts/ze-proactive/ze_proactive/notifier.py   # B4: claim payload = body
core/cognition/ze-worldstate/ze_worldstate/{surfacing.py, bootstrap.py}   # B4
core/arbitration/ze-priority/ze_priority/{view.py, types.py, rest.py, turn.py, tools.py, service.py, contribution.py, arbitration.py}   # B5
core/automation/ze-automation/ze_automation/
├── goals/{lifecycle.py (new), __init__.py, executor.py}   # B14, B1
├── agents/goals/tools.py               # B14
├── bootstrap.py                        # B1 (GoalExecutor tz), B11 (workflow failure), B13
└── jobs/{goal_narrative.py, accountability.py}   # B11
plugins/ze-personal/ze_personal/jobs/briefing.py  # B11
plugins/ze-calendar/ze_calendar/reminders/{calendar.py, calendar_store.py}   # B11 calendar
apps/ze-web/src/
├── entities/conversation/model/reducer.ts       # B10
├── features/respond-to-confirmation/ui/ConfirmationFrameHandler.tsx   # B10
└── features/turn-stream/{ui/TurnFrameHandler.test.tsx, model/frame-registry.ts}   # B10
```

**Structure Decision**: fixes stay in the package that owns the behaviour. The only new source file is `ze_automation/goals/lifecycle.py`, which phase 211 grows into the full goal lifecycle module.

### Blast radius (`graphify affected … --depth 2`, plus grep where graphify had no node)

| Symbol changed | Callers outside the owning package |
|---|---|
| `_execute_single`, `_execute_compound` | only `execute_tool`; tests in ze-core (`test_execution*`, `test_tool_sink`) and ze-api (`test_priority_confirmation_flow`) |
| `GoalExecutor.__init__` | `ze_automation/bootstrap.py:164` and about 10 ze-automation tests (the new parameter has a default, so they do not change) |
| `ZeContainer._build_config` | `ze_core/container.py:113,180`, `conversation/turn.py:274,479`, `wiring/container.py:396`, `api/eval/router.py:106`, `ws/confirmation.py:130` (graphify conflated it with `migrate.py::_build_config`; grep used) |
| `_ContainerTurnStarter` | ze-api only: `build_container`, `lifespan`, `cli/seed`, 6 tests in `test_workspace_followthrough.py` |
| `LoopSurfacer`, `build_loop_surfacer` | ze-api `wiring/container.py:532`, `tests/pg/test_acceptance.py:64`, `tests/pg/test_loop_evidence.py:146`; ze-priority `arbitration.py`, `test_arbitration.py` |
| `ProactiveNotifier.notify` (claim payload only) | every proactive job; the payload has no reader, so no caller changes |
| `PriorityView` | ze-priority `rest`, `service`, `tools`, `turn`, `arbitration`, `agent`, `compose/composer`; ze-api `wiring/container.py:465`, `wiring/agents.py:191-202`, `api/v0/priority/router.py`, pg tests `test_acceptance`, `test_loop_confirmation_pg`, `test_stuck_goals`, `agents/test_bootstrap`; ze-personal `jobs/briefing.py` |
| `TurnSurfacing.__init__` (loses `override_store`) | ze-api `wiring/container.py`; ze-priority `test_turn.py` |
| `write_memory`, `record_trace` | graph wiring; ze-core tests `test_memory`, `test_judgment_bars`, `test_extractor_dual_write`, `test_retry_rewind`, `test_turn_telemetry_stamp`, `test_record_trace`, `test_trace_*`; ze-api `test_retry_rollback_e2e` |
| `AgentState.compaction_span` | `nodes/trace.py`, `nodes/memory.py`, `test_trace_memory_chunks.py` |
| `invoke_raw_turn`, `resume_turn` (B15) | ze-api `_locked_invoke_raw_turn`, `_locked_resume_turn` (`wiring/container.py:213`, `:227`); ze-core tests `test_tool_sink`, `test_turn_telemetry_stamp`, `test_resume_turn_request_id`, `test_conversation_turn`, `test_screen_trace`; ze-api `test_workspace_followthrough`. Fake containers in those tests may lack `_abort_tokens`; the turn reads it with `getattr` and runs without cancel when it is absent, as it already runs untimed without a telemetry registry |
| `automation_data_domains` | ze-api `build_container`, `lifespan`, `cli/seed`, container tests |
| `pause_goal`, `abandon_goal` | none (reached through tool registration only) |

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first): `ZeApiSettings.timezone` with its test (T002–T003). Every other lane builds against the current code; the B4 and B5 constructor changes are wired into `wiring/container.py` by `lead` when those lanes merge (T040–T041).

| Lane | Model / role | Owns (files and dirs, disjoint) | Tasks | Starts after | Reviewer |
|------|--------------|---------------------------------|-------|--------------|----------|
| lead | Sonnet ENG lead | `apps/ze-api/ze_api/settings.py`, `apps/ze-api/ze_api/wiring/container.py`, `apps/ze-api/tests/test_settings_timezone.py`, `apps/ze-api/tests/test_container_config.py`, `apps/ze-api/tests/api/test_workspace_followthrough.py`, `apps/ze-api/tests/test_container_tier_judge.py`, `apps/ze-api/ze_api/api/v0/priority/router.py`, `apps/ze-api/tests/pg/`, `apps/ze-api/tests/agents/test_bootstrap.py`; integration, final gates | T001–T003, T009–T012, T040–T043 | - | floor reviewer (Maestro assigns) |
| engine | Sonnet ENG | `core/engine/ze-core/ze_core/orchestration/nodes/execution.py`, `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` (lines 252-342 only), `core/engine/ze-core/ze_core/orchestration/nodes/trace.py`, `core/engine/ze-core/ze_core/orchestration/state.py`, `core/contracts/ze-agents/ze_agents/delegate.py`, `core/engine/ze-core/tests/orchestration/nodes/test_execution.py`, `core/engine/ze-core/tests/orchestration/test_compaction_readout.py`, `core/engine/ze-core/tests/orchestration/nodes/test_trace_memory_chunks.py`, `core/engine/ze-core/tests/orchestration/nodes/test_memory.py`, `core/contracts/ze-agents/tests/test_delegate.py`, `core/engine/ze-core/ze_core/conversation/turn.py`, `core/engine/ze-core/tests/conversation/test_turn_abort.py` | T004–T006, T032–T034, T046–T047 | contract step | floor reviewer (Maestro assigns) |
| automation | Sonnet ENG | `core/automation/ze-automation/ze_automation/goals/lifecycle.py`, `core/automation/ze-automation/ze_automation/goals/__init__.py`, `core/automation/ze-automation/ze_automation/goals/executor.py`, `core/automation/ze-automation/ze_automation/agents/goals/tools.py`, `core/automation/ze-automation/ze_automation/bootstrap.py`, `core/automation/ze-automation/ze_automation/jobs/goal_narrative.py`, `core/automation/ze-automation/ze_automation/jobs/accountability.py`, `apps/ze-api/ze_api/api/ws/goal_actions.py`, `core/automation/ze-automation/tests/goal_agent/`, `core/automation/ze-automation/tests/goal_engine/test_executor.py`, `core/automation/ze-automation/tests/goal_engine/test_lifecycle.py`, `core/automation/ze-automation/tests/proactive_jobs/`, `core/automation/ze-automation/tests/workflow_engine/test_failure_handler.py`, `apps/ze-api/tests/api/test_goal_actions.py`, `apps/ze-api/tests/test_data_domains_unique.py` | T007–T008, T013–T017, T028–T029, T038–T039 | contract step | floor reviewer (Maestro assigns) |
| attention | Sonnet ENG | `core/arbitration/ze-priority/ze_priority/`, `core/arbitration/ze-priority/tests/`, `core/cognition/ze-worldstate/ze_worldstate/surfacing.py`, `core/cognition/ze-worldstate/ze_worldstate/bootstrap.py`, `core/cognition/ze-worldstate/tests/test_surfacing.py`, `core/contracts/ze-proactive/ze_proactive/notifier.py`, `core/contracts/ze-proactive/tests/test_notifier.py`, `plugins/ze-personal/ze_personal/jobs/briefing.py`, `plugins/ze-personal/tests/jobs/test_briefing.py`, `plugins/ze-calendar/ze_calendar/reminders/calendar.py`, `plugins/ze-calendar/ze_calendar/reminders/calendar_store.py`, `plugins/ze-calendar/tests/jobs/test_reminders.py` | T018–T027, T030–T031 | contract step | floor reviewer (Maestro assigns) |
| web | Haiku JR | `apps/ze-web/src/entities/conversation/model/reducer.ts`, `apps/ze-web/src/entities/conversation/model/reducer.test.ts`, `apps/ze-web/src/features/respond-to-confirmation/ui/ConfirmationFrameHandler.tsx`, `apps/ze-web/src/features/turn-stream/ui/TurnFrameHandler.test.tsx`, `apps/ze-web/src/features/turn-stream/model/frame-registry.ts` | T035–T037 | - | floor reviewer (Maestro assigns) |
| docs | Haiku DOCS | `docs/configuration.md`, `docs/goals.md`, `docs/workspace.md`, `docs/data-portability.md`, `docs/scheduled-jobs.md`, `docs/cognitive-architecture.md`, `docs/native-interface.md`, `core/arbitration/ze-priority/README.md`, `core/cognition/ze-worldstate/README.md`, `AGENTS.md`, `specs/README.md` (198 Status cell only) | T044–T045 | all lanes merged | floor reviewer (Maestro assigns) |

**Rules**: one lane per file; `lead` owns `wiring/container.py` and `settings.py`, and other lanes request changes there; `engine` owns only lines 252-342 of `nodes/memory.py` (phase 199 owns 199-223; keep hunks apart, and ask Ledger through the Maestro before touching anything else in that file); each lane works on a sub-branch of the floor branch, and `lead` merges web → engine → automation → attention → docs, then runs T040–T043; each lane is reviewed as it finishes; the `web` lane is Haiku because its tasks carry the exact change and the exact failing tests.

## Complexity Tracking

None.

## Analysis

`/speckit-analyze`, 2026-10-22, after clarify and the B15 addition. No CRITICAL or HIGH findings; no constitution conflict. Fixed in place:

| ID | Severity | Finding | Fix |
|----|----------|---------|-----|
| A1 | MEDIUM | US1 scenario 4 (workflow step zone) had no test | T002 (f) runs `fetch_context` with the application settings |
| A2 | MEDIUM | SC-005 promised a test per consumer; composer had none | T023 adds a composer ordering test; SC-005 names the tested consumers |
| A3 | LOW | SC-001 promised one parametrized test across packages | Reworded: one failing test per path |
| A4 | LOW | FR-026 implied a REST change; the snapshot already carries `computed_rank` | Reworded: no REST change |
| A5 | LOW | Decayed-override edge case untested | T022 (d) |
| A6 | LOW | US3 timeout scenario had no task | T011 notes it is the reused function's tested behaviour |

Coverage: 27 of 27 functional requirements and 12 of 12 success criteria have tasks; 47 tasks, all lane-tagged; no unmapped tasks.
