# Tasks: Audit Bug Fixes

**Input**: [spec.md](./spec.md), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [quickstart.md](./quickstart.md). No data model, no contracts, no migration.

**Tests**: required (constitution V, spec FR-025). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. No real database (`AsyncMock` pools) and no real model calls.

## Format: `[ID] [P?] [Lane] [Area] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:engine]`, `[L:automation]`, `[L:attention]`, `[L:web]`, `[L:docs]` (plan.md Lane Plan). A task touches only files its lane owns.
- **[Area]**: `[BE]` backend, `[WEB]` ze-web, `[PLATFORM]` wiring and gates, `[DOCS]` documentation.
- **[Story]**: US1 timezone (B1), US2 turn extractor (B2), US3 follow-up confirmation (B9), US4 goal lifecycle (B14), US5 user's order (B5), US6 loop push bar (B4), US7 cooldowns (B11), US8 compaction readout (B6), US9 rail dot (B10), US10 data domains (B13), US11 Cancel (B15).

**Crew**: Sonnet `lead`, `engine`, `automation`, `attention`; Haiku `web` (fully specified) and `docs`. The contract step (T001–T003) lands first; the other lanes then run in parallel in their own worktrees; `lead` merges web → engine → automation → attention, runs T040–T043, then `docs` runs. Tick a task's checkbox in the same commit that finishes it.

**Rules for every lane**: `graphify affected "<Symbol>" --depth 2` before changing a shared symbol; typed `ZeError`s; `get_logger(__name__)`; `git add <paths>`, never `-A`, `stash` or `reset`. `engine` edits `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` only in lines 252-342; phase 199 (Ledger) owns 199-223.

---

## Phase 1: Setup and contract step (lane `lead`)

- [ ] T001 [L:lead] [PLATFORM] `make install`; `graphify update .`; re-read every file:line in spec.md "Context" against the floor branch and note any drift in the Handoffs note. Confirm with Ledger, through the Maestro, which commit of floor 199 touches `nodes/memory.py`, so the engine lane can rebase onto it if it lands first.
- [x] T002 [L:lead] [BE] [US1] Tests first, new `apps/ze-api/tests/test_settings_timezone.py`: (a) YAML `timezone: Europe/Lisbon` with `TIMEZONE=America/New_York` set → `ZeApiSettings(...).timezone == "Europe/Lisbon"`; (b) no YAML key, `TIMEZONE=America/New_York` → `"America/New_York"`; (c) neither → `"UTC"`; (d) `TIMEZONE=Not/AZone` → `"UTC"` and one `settings_timezone_invalid` warning; (e) `to_core_settings().timezone == settings.timezone` in each case; (f) `fetch_context` (helpers `_config` and `_state` from `core/engine/ze-core/tests/orchestration/nodes/test_context.py`) run with a `ZeApiSettings` whose zone is `Europe/Lisbon` builds an agent context with that zone. This covers conversation turns and workflow steps, which both read the zone through `fetch_context`. Use `monkeypatch.setenv` and the copied-YAML settings fixture pattern from `docs/testing.md`. They fail today (no attribute).
- [x] T003 [L:lead] [BE] [US1] Implement `ZeApiSettings.timezone` in `apps/ze-api/ze_api/settings.py` (YAML, then env, then UTC; validated with `zoneinfo.ZoneInfo`), and make `to_core_settings()` use it. T002 passes; `make test` green.

**Checkpoint**: contract step merged; every lane branches from here.

---

## Phase 2: User Story 1 — the user's timezone everywhere (P1)

**Goal**: every agent context that builds a prompt carries the configured zone (FR-001–FR-004).

- [ ] T004 [P] [L:engine] [BE] [US1] Tests first in `core/engine/ze-core/tests/orchestration/nodes/test_execution.py` (helpers `_register_and_wire`, `_envelope`, `_ctx`): with `base_ctx.timezone = "Europe/Lisbon"`, the agent receives `ctx.timezone == "Europe/Lisbon"` for a single-agent envelope and for both subtasks of a compound envelope. Fails today (UTC).
- [ ] T005 [P] [L:engine] [BE] [US1] Test first in `core/contracts/ze-agents/tests/test_delegate.py`: a delegate from a context with `timezone="Europe/Lisbon"` gives the specialist a context with the same zone. Fails today.
- [ ] T006 [L:engine] [BE] [US1] Pass `timezone=base_ctx.timezone` at `core/engine/ze-core/ze_core/orchestration/nodes/execution.py:388` and `:493`, and `timezone=ctx.timezone` at `core/contracts/ze-agents/ze_agents/delegate.py:270`. T004–T005 pass.
- [x] T007 [P] [L:automation] [BE] [US1] Test first in `core/automation/ze-automation/tests/goal_engine/test_executor.py`: build the `executor` fixture with `timezone="Europe/Lisbon"`, run one milestone, capture the context through the `agent_getter` mock, assert its zone. Fails today (no parameter).
- [x] T008 [L:automation] [BE] [US1] Add `timezone: str = "UTC"` to `GoalExecutor.__init__` (`ze_automation/goals/executor.py:168`), use it at `:906`, and pass `settings.timezone` at `ze_automation/bootstrap.py:164`. T007 passes.

**Checkpoint**: `make test-core`, `make test-agents`, `make test-automation`, `make test` green.

---

## Phase 3: User Story 2 — turn extractor (P1)

- [ ] T009 [L:lead] [BE] [US2] Test first, new `apps/ze-api/tests/test_container_config.py`: build a `ZeContainer` with the `_container()` pattern from `test_container_tier_judge.py`, but call the real `ZeContainer._build_config("t1")`. Assert (a) `configurable["turn_extractor"] is gather_turn_proposals`; (b) every key of `Container._build_config(c, "t1")["configurable"]` is present in the ze-api one, and the failure message names the missing keys. Both fail today (`turn_extractor`).
- [ ] T010 [L:lead] [BE] [US2] Add `"turn_extractor": gather_turn_proposals` beside `fact_extractor` in `apps/ze-api/ze_api/wiring/container.py:322`. T009 passes.

---

## Phase 4: User Story 3 — follow-up confirmation (P1)

- [ ] T011 [L:lead] [BE] [US3] Test first in `apps/ze-api/tests/api/test_workspace_followthrough.py`, reusing `_LockAwareFakeContainer`, `_FakeTurnOutcome` and the `test_components_only_followup_turn_is_delivered` pattern. Give the fake container `connection_manager`, `confirmation_store`, `notifier` and `settings.confirm_timeout_seconds`. Outcome `interrupted=True` with one confirmation item (shape from `test_ws_write_confirmation.py::test_interrupted_turn_sends_items_frame_and_saves_the_row`). Assert one `confirm_request` frame on the thread, `confirmation_store.save` awaited once, `notifier.notify` called with `CONFIRMATION_REQUEST`, and a timeout task started. Second case: no client connected → no frame, row saved, push sent. Fails today (nothing sent). The timeout path (US3 scenario 3) is the existing `send_confirmation_request` behaviour, already covered by its WS tests; assert only that the timeout task is started.
- [ ] T012 [L:lead] [BE] [US3] In `_ContainerTurnStarter.invoke_raw_turn` (`apps/ze-api/ze_api/wiring/container.py:161`), when `outcome.interrupted`, call `send_confirmation_request(container.connection_manager, container, outcome, thread_id, confirmation_store=container.confirmation_store)` (local import) and return. No lock (`test_turn_lock_wiring.py` stays green). T011 passes.

---

## Phase 5: User Story 4 — goal lifecycle (P1)

- [x] T013 [P] [L:automation] [BE] [US4] Tests first, new `core/automation/ze-automation/tests/goal_engine/test_lifecycle.py`: a table over all six `GoalStatus` values. `can_pause` is true only for `active`, `awaiting_gate`; `can_abandon` for `planning`, `active`, `awaiting_gate`, `paused`; `can_resume` only for `paused`.
- [x] T014 [L:automation] [BE] [US4] New `core/automation/ze-automation/ze_automation/goals/lifecycle.py` with the three pure functions; export them from `ze_automation/goals/__init__.py`. T013 passes.
- [x] T015 [P] [L:automation] [BE] [US4] Tests first in `core/automation/ze-automation/tests/goal_agent/test_goal_agent.py`, beside `test_run_pauses_goal_via_tool`: parametrize over all six statuses for `pause_goal` and `abandon_goal`, called directly with a mocked store. Refused → result has `error`, `update_status` and `close_holds` not awaited, no `undo` key. Allowed → as today (pause still returns `undo_payload`). Pause on `completed` fails today.
- [x] T016 [L:automation] [BE] [US4] Guard `pause_goal` and `abandon_goal` in `ze_automation/agents/goals/tools.py` (`:230-244`, `:323-332`) with `can_pause`/`can_abandon`, error text "<title> is <status>; it cannot be paused." / "… abandoned."; `resume_goal` (`:255-271`) uses `can_resume`. T015 passes; `apps/ze-api/tests/test_undo_payload_contract.py` stays green.
- [x] T017 [L:automation] [BE] [US4] Test first in `apps/ze-api/tests/api/test_goal_actions.py`: the same six-status table through the WS pause and abandon actions, asserting the same allow/refuse outcome as T015. Then replace the inline checks in `apps/ze-api/ze_api/api/ws/goal_actions.py:207-232` with the lifecycle functions, keeping the "Goal already resolved." reply.

---

## Phase 6: User Story 5 — the user's order (P2)

- [ ] T018 [P] [L:attention] [BE] [US5] Tests first in `core/arbitration/ze-priority/tests/test_view.py` (override fixtures from `test_merge.py`, factories from `tests/factories.py`): with a fake override store returning one pinned override that puts B above A (A computes higher), `rank()` returns B before A, `B.rank == 1`, `B.computed_rank == 2`, `B.override` set. Override store raising → computed order and one `priority_overrides_unavailable` warning. No override store reads when there are no items.
- [ ] T019 [L:attention] [BE] [US5] `PriorityView.__init__(…, override_store, clock=…)`; `rank()` merges with `merge.py`; `PriorityItem` gains `computed_rank: int` and `override: PriorityOverride | None` (`ze_priority/types.py`). T018 passes.
- [ ] T020 [L:attention] [BE] [US5] Update `test_rest.py` and `test_turn.py` first: the snapshot and `TurnSurfacing` no longer read the override store, and their output order is the view's. Then drop the merge calls from `ze_priority/rest.py:26-29` and `ze_priority/turn.py:202-218`; `TurnSurfacing` loses `override_store` (hard cut). `MergedPriorityItem` is built from the item's fields.
- [ ] T021 [L:attention] [BE] [US5] Tests first: `test_tools.py` — after the user moved B to the top, `reprioritize_item("B", "more_urgent")` answers that B is already the most urgent and submits nothing; `test_service.py` — the collision contribution states B's computed position. Then make `_resolve_anchor` (`ze_priority/tools.py:57`) use the displayed rank and `contribution.py:39` read `computed_rank`.
- [ ] T022 [L:attention] [BE] [US5] Tests first in `core/arbitration/ze-priority/tests/test_arbitration.py` with a real `PriorityView` over the fake override store: (a) user order B above A → B is sent first; (b) the item the user pushed down is never sent, even when it is the only candidate (clarify Q3); (c) budget 0 with pins → nothing sent; (d) an unpinned override that has decayed to zero weight does not exclude its item. Then make `rank_subset` (`ze_priority/arbitration.py:62`) order candidates by their place in the full `rank()` and drop pushed-down items (active override, weight > 0, `rank > computed_rank`).
- [ ] T023 [L:attention] [BE] [US5] Update `core/arbitration/ze-priority/tests/compose/test_composer.py` and `test_performance.py` for the new constructor, and add one composer test: with the user's override placing person B above person A, the slipping answer's relationship cards list B first (fails today). The composer and the briefing need no code change. `make test-priority` and `make test-personal` green.

---

## Phase 7: User Story 6 — loop push bar (P2)

- [ ] T024 [P] [L:attention] [BE] [US6] Test first in `core/contracts/ze-proactive/tests/test_notifier.py`: a discretionary push claims with `payload == body`. Then change `notifier.py:150` to `payload=body`.
- [ ] T025 [L:attention] [BE] [US6] Tests first in `core/cognition/ze-worldstate/tests/test_surfacing.py` (reuse `_RecordingNli`, `_push_bar_surfacer`, the `surfacing._fetch_evidence_summaries` monkeypatch, and an in-memory push log modelled on the `_PushLog` fake in `ze-priority/tests/test_turn.py:311`, extended with `list_recent_payloads`): (a) built through `build_loop_surfacer(…, nli_client=_RecordingNli(score=0.01))`, `eligible_candidates(thresholds={})` with no NLI argument returns `[]` for a loop whose evidence does not support its title; (b) an `attention_push` row whose payload is a near-identical hedged mention, 3 hours old, excludes the loop; (c) a `worldstate_loop_push` row has no effect. (a) and (b) fail today.
- [ ] T026 [L:attention] [BE] [US6] `LoopSurfacer.__init__` and `build_loop_surfacer` (`ze_worldstate/bootstrap.py:74-92`) take `nli_client`; remove the `nli_client` parameter from `passes_push_bar` and `eligible_candidates`; novelty compares `format_hedged_mention(loop.title, rationale)` with `list_recent_payloads(ATTENTION_PUSH_EVENT_KEY, 48)`; delete `PUSH_EVENT_KEY`. Update `ze_priority/arbitration.py:43` if it passes NLI. T024–T025 pass.
- [ ] T027 [L:attention] [BE] [US6] Test in `core/arbitration/ze-priority/tests/test_arbitration.py`: `AttentionArbitrationJob.run` with a real `LoopSurfacer` (fake stores, `_RecordingNli`) sends nothing for an ungrounded loop and nothing for a repeated one, with no direct call to a bar function (SC-006).

---

## Phase 8: User Story 7 — cooldowns (P2)

- [ ] T028 [P] [L:automation] [BE] [US7] Tests first, parametrized over `failed` / `delivered` / `held`: `tests/proactive_jobs/test_goal_narrative.py` (`_make_job`) and `tests/proactive_jobs/test_accountability.py` (`_make_accountability_job`). `failed` → `push_log.log` not awaited; the other two → awaited once. Set `notify.return_value = "delivered"` in the existing "writes push log" tests (`test_goal_narrative.py:121`, `test_accountability.py:150`). Then gate the writes in `ze_automation/jobs/goal_narrative.py:87-93` and `jobs/accountability.py:51-56` on `outcome in ("delivered", "held")`.
- [ ] T029 [L:automation] [BE] [US7] Tests first in `core/automation/ze-automation/tests/workflow_engine/test_failure_handler.py` (`_handler`): (a) every failure logs `workflow_failure:<id>` whatever the outcome; (b) the alert cooldown reads and writes `workflow_failure_alert:<id>`, written only after `delivered`/`held`; (c) a failure whose alert failed, followed by a second failure inside the cooldown, alerts again. Then change `ze_automation/bootstrap.py:225-246`. Fix `test_failure_handler.py:57` (`return_value="delivered"`).
- [ ] T030 [P] [L:attention] [BE] [US7] Tests first in `plugins/ze-personal/tests/jobs/test_briefing.py` (`make_briefing`, `make_notifier`), parametrized as T028; fix `test_briefing.py:140`. Then gate `ze_personal/jobs/briefing.py:119-125`.
- [ ] T031 [L:attention] [BE] [US7] Tests first (clarify Q2) in `plugins/ze-calendar/tests/jobs/test_reminders.py`: `fire_reminder` with a notifier returning `failed` calls `mark_unsent(reminder_id)`; `delivered` does not. Add `CalendarReminderStore.mark_unsent` (`UPDATE calendar_reminders SET sent = false, sent_at = NULL WHERE id = $1`) in `ze_calendar/reminders/calendar_store.py` and call it from `ze_calendar/reminders/calendar.py:176-189`.

---

## Phase 9: User Story 8 — compaction readout (P3)

- [ ] T032 [L:engine] [BE] [US8] Test first, new `core/engine/ze-core/tests/orchestration/test_compaction_readout.py`, beside `test_preset_graph.py`: `graph_builder` with noop node overrides, `MemorySaver`, `make_graph_input`, and the long history from `test_context_continuity_composition.py:50-56` (a 100k-character message, `model="unknown/model"`, a client mock returning `"condensed summary"`). Run four turns on one thread; compaction happens after turn 1. Assert (clarify Q1): turn 1 `compaction is None`; turns 2, 3 and 4 show `CompactionTrace(0, k)`. A fifth turn after a second compaction shows the newer span. Fails today on turns 3 and 4.
- [ ] T033 [L:engine] [BE] [US8] In `nodes/memory.py` `_compact` (`:320-342`), put `"compaction_span": [0, len(older_span) - 1]` on the summary message; remove `compaction_span` from `write_memory`'s returns (`:284-294`). In `nodes/trace.py:79-84`, derive `compaction` from `state["messages"][0]` when it carries `compaction_summary`. Remove `compaction_span` from `AgentState` (`orchestration/state.py`). Check that the extra key never reaches the provider payload (the existing `compaction_summary` key shows how history dicts are sent; strip both if they are sent). T032 passes.
- [ ] T034 [L:engine] [BE] [US8] Rewrite `core/engine/ze-core/tests/orchestration/nodes/test_trace_memory_chunks.py:102-158` to feed a history that opens with a summary message instead of setting `compaction_span` by hand. `make test-core` green.

---

## Phase 10: User Story 9 — rail dot (P3, lane `web`)

- [ ] T035 [P] [L:web] [WEB] [US9] Tests first in `apps/ze-web/src/entities/conversation/model/reducer.test.ts`, in the "pause, attention, bookkeeping" block (`:145`): `paused` on a thread that is not active sets `attention: true` (for a running thread and for an unknown one); `paused` on the active thread leaves `attention: false`. The existing "idle stays idle" assertion (`:147`) keeps passing for the phase.
- [ ] T036 [P] [L:web] [WEB] [US9] Tests first in `apps/ze-web/src/features/turn-stream/ui/TurnFrameHandler.test.tsx` (its `useFrame` mock, `emit`, `confirmFrame`, `wrap`, `useWsStore` reset): render `<><ConfirmationFrameHandler/><TurnFrameHandler/></>` (shell order). Emit `typing` on `t2`, then `confirmFrame({thread_id: "t2"})` → `attentionThreads.t2 === true`, `thinkingThreads.t2 === false`, card in `usePendingConfirms.getState().byThread.t2`; then `act(() => useSession.setState({threadId: "t2"}))` → attention false. Variant: `t2` never seen before. Fails today at the first attention assertion.
- [ ] T037 [L:web] [WEB] [US9] In `apps/ze-web/src/entities/conversation/model/reducer.ts:300-303`, `paused` returns `{ ...(isRunning(t) ? { ...t, turn: { ...t.turn, phase: "paused" } } : t), attention: t.attention || event.threadId !== ctx.activeThreadId }`. Delete the `useWsStore` setters in `apps/ze-web/src/features/respond-to-confirmation/ui/ConfirmationFrameHandler.tsx` (`:7-8`, `:17`, `:19`). Fix the `confirm_request` reason in `apps/ze-web/src/features/turn-stream/model/frame-registry.ts:73`. T035–T036 pass; `make test-web` and `make typecheck-web` green.

---

## Phase 11: User Story 10 — data domains (P3)

- [ ] T038 [L:automation] [BE] [US10] Test first, new `apps/ze-api/tests/test_data_domains_unique.py`: build the list the container builds (`engine_data_domains`, `automation_data_domains`, `worldstate_data_domains`, `feedback_data_domains`, `interruption_data_domains`, `PersonalPlugin.data_domains(PersonalPlugin.__new__(PersonalPlugin))`) over a fake pool that records SQL (pattern in `plugins/ze-personal/tests/test_data_domains.py`). Assert each table is registered once, `export()` selects each table once, and `delete()` runs `DELETE FROM goals` in a later batch than `DELETE FROM open_loops`. Fails today.
- [ ] T039 [L:automation] [BE] [US10] Delete the `automation.goals` and `automation.workflows` entries from `automation_data_domains` (`ze_automation/bootstrap.py:84-140`); keep `automation.accountability`. T038 passes.

---

## Phase 11b: User Story 11 — Cancel stops the turn (P2, lane `engine`)

- [ ] T046 [L:engine] [BE] [US11] Tests first, new `core/engine/ze-core/tests/conversation/test_turn_abort.py`, with a fake container in the style of `test_turn_telemetry_stamp.py` (a real core `Container`'s `_abort_tokens` and `abort_invocation`, a fake graph whose `astream_events` / `ainvoke` captures `config["configurable"]["abort_token"]` and waits on an `asyncio.Event`). Cases: (a) during `invoke_raw_turn` on T, `container.abort_invocation(T)` sets the captured token; (b) the same during `resume_turn`; (c) after the turn ends, `_abort_tokens` has no entry for T; (d) with turns on T1 and T2 running, aborting T1 leaves T2's token unset; (e) a turn that ends while a newer token for T is registered leaves the newer one in place; (f) a container without `_abort_tokens` still runs the turn. (a), (b) and (d) fail today.
- [ ] T047 [L:engine] [BE] [US11] In `core/engine/ze-core/ze_core/conversation/turn.py`, add a helper that creates an `AbortToken`, registers it in `getattr(container, "_abort_tokens", None)` under the thread, and removes it in `finally` only if the stored token is still this one. `invoke_raw_turn` (`:261-274`) passes it as `abort_token` in the `_build_config` extras; `resume_turn` (`:384`) adds it to `config["configurable"]` before `ainvoke`. T046 passes; `test_tool_sink.py`, `test_turn_telemetry_stamp.py`, `test_resume_turn_request_id.py`, `test_conversation_turn.py` and ze-api `test_workspace_followthrough.py` stay green.

---

## Phase 12: Integration and gates (lane `lead`)

- [ ] T040 [L:lead] [PLATFORM] [US6] After `attention` merges: pass `shared.nli_client` to `build_loop_surfacer` at `apps/ze-api/ze_api/wiring/container.py:532`; update `apps/ze-api/tests/pg/test_acceptance.py:64` and `apps/ze-api/tests/pg/test_loop_evidence.py:146`.
- [ ] T041 [L:lead] [PLATFORM] [US5] After `attention` merges: pass `override_store=stores.priority_override_store` to `PriorityView` (`wiring/container.py:465`); stop passing it to `TurnSurfacing` and to the REST snapshot (`apps/ze-api/ze_api/api/v0/priority/router.py`); update `apps/ze-api/tests/agents/test_bootstrap.py` and the pg tests `test_loop_confirmation_pg.py`, `test_stuck_goals.py` that build these.
- [ ] T042 [L:lead] [PLATFORM] Gates: `make test-py`, `make test-web`, `make typecheck-web`, `make lint`, and `make test-pg` when Docker is available. Record the results in the Handoffs note.
- [ ] T043 [L:lead] [PLATFORM] `graphify update .`, then `graphify affected` on every changed public symbol (`PriorityView`, `PriorityItem`, `TurnSurfacing`, `LoopSurfacer`, `build_loop_surfacer`, `GoalExecutor`, `ZeApiSettings`, `AgentState`, `invoke_raw_turn`, `resume_turn`) and confirm no caller was missed. `git diff main...HEAD -- core/engine/ze-core/ze_core/orchestration/nodes/memory.py` shows no hunk in lines 199-223.

---

## Phase 13: Docs (lane `docs`, after all lanes merged)

- [ ] T044 [L:docs] [DOCS] Update every public doc the phase changes, per the `doc-style` skill:
  - `docs/configuration.md:56`: `TIMEZONE` (and the YAML `timezone` key) now set the zone of every agent, goal milestone and workflow step, not only calendar and reminders;
  - `docs/goals.md` (around `:59-62`): pause works on active or gate-waiting goals, abandon on unfinished goals, resume on paused goals, the same in chat and on the goal's screen;
  - `docs/workspace.md:42`: a follow-up turn that asks first shows the confirmation card or sends a push;
  - `docs/data-portability.md`: the archive holds goals and workflows once (`goals.goals.json`, `workflow.workflows.json`);
  - `docs/scheduled-jobs.md`: a failed brief, narrative, accountability summary or workflow alert is retried on the next run; a failed calendar reminder is sent late, at the next startup;
  - `docs/cognitive-architecture.md:101`: `PriorityView` returns the user's order, and arbitration follows it;
  - `core/arbitration/ze-priority/README.md:11-14`: overrides merge inside `PriorityView.rank()`; items keep `computed_rank`;
  - `core/cognition/ze-worldstate/README.md:23`: `LoopSurfacer` takes the NLI client; novelty reads the governor's pushes;
  - `docs/native-interface.md:70`: the `cancel` command stops the running or resumed turn on that thread, not only a pending confirmation.
- [ ] T045 [L:docs] [DOCS] Add the phase 198 row to the `AGENTS.md` phase table (Implemented, one paragraph naming the eleven fixes). In `specs/README.md`, edit only the Status cell of row 198. Coverage check: `git diff --stat main...HEAD` — every changed package with a README or doc listed in T044 has a matching doc change, or a line in the Handoffs note saying why none was needed.

---

## Dependencies and order

- T001–T003 (contract step) before every other lane. Inside each lane, every "tests first" task precedes its implementation task.
- `engine`, `automation`, `attention` and `web` run in parallel; their files are disjoint.
- T040–T041 after `attention` merges; T042–T043 after every lane merges; T044–T045 last.
- Phase 199's change to `nodes/memory.py` may land first: `engine` rebases and keeps its hunks in 252-342.

## Parallel example

```text
engine:     T004, T005 → T006 → T032 → T033 → T034; T046 → T047
automation: T007 → T008; T013 → T014; T015 → T016 → T017; T028; T029; T038 → T039
attention:  T018 → T019 → T020 → T021 → T022 → T023; T024; T025 → T026 → T027; T030; T031
web:        T035, T036 → T037
```
