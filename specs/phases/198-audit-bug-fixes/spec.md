# Feature Specification: Audit Bug Fixes

**Feature Branch**: `198-audit-bug-fixes`

**Created**: 2026-10-22

**Status**: Ready to implement

**Wave**: 0 (architecture review 2026-10). Phases 200, 201, 202–207, 211, 214 and 217 build on it.

**Input**: Architecture review 2026-10-22, bugs B1, B2, B4, B5, B6, B9, B10, B11, B13 and B14, plus B15 (added by the user on 2026-10-22: Cancel never stops a running WS turn). Each is a small fix. Each fix starts with a failing test through the real interface: the graph, the container, the job's `run`, the tool, the WS action, or the frame handler. This phase repairs behaviour only. The deepening behind each fix belongs to a later phase: 200 (agent context derivation), 201 (typed turn services), 204 (push bar and cooldowns), 205 (web turn state), 207 (conversation turn module), 211 (personal unbundling) and 217 (data domain factory).

**Doctrine functions served**: Action (B1, B9, B14, B15), Memory (B2, B6), Executive and Governance (B4, B5, B11), Governance (B13). Perception through the web shell (B10).

## Context *(verified against the code, 2026-10-22)*

Each audit claim was read against the code at the floor's base commit `c8dc97da`. Paths are relative to the package roots named in `AGENTS.md`. Where the audit was wrong, the correction is stated.

### B1: agents always see UTC (TRUE, and wider than reported)

- Subtask contexts drop `timezone`: `ze_core/orchestration/nodes/execution.py:388` (`_execute_single`) and `:493` (`_make_ctx` in `_execute_compound`). `AgentContext.timezone` defaults to `"UTC"` (`ze_agents/types.py:188`).
- **Correction: the parent context is UTC too.** `fetch_context` reads `getattr(cfg, "timezone", None)` (`nodes/context.py:332-345`) from `config["configurable"]["settings"]`. In ze-api that is `ZeApiSettings` (`wiring/container.py:330`), which has no `timezone` attribute. Only `ZeApiSettings.to_core_settings()` (`ze_api/settings.py:131-142`) reads the YAML `timezone` key or the `TIMEZONE` env var. So every conversation turn and every workflow run (`ze_automation/bootstrap.py:278` hands over the same settings) builds a UTC context.
- A third copy drops it: `ze_agents/delegate.py:270` (the conductor's delegate to a specialist).
- Goal milestones build `AgentContext` by hand without it: `ze_automation/goals/executor.py:906`. `GoalExecutor.__init__` (`:168`) takes no timezone. It is built at `ze_automation/bootstrap.py:164`, where settings are in scope.
- `ui_actions.py:152` and `base_agent.py:355` (`run_undo`) also omit it, but they make no model call and build no prompt.
- **What the user sees**: `BaseAgent._build_system_prompt` (`base_agent.py:251`) writes "Current date and time … UTC". Calendar and reminders also pass the configured zone as a prompt extra (`calendar/agent.py:83`, `reminders/agent.py:78`), so their prompts mix a UTC "now" with a local zone.

### B2: conversation turns write no memory events or entities (TRUE)

- Core `Container._build_config` (`ze_core/container.py:51-68`) sets `turn_extractor`. `ZeContainer._build_config` (`ze_api/wiring/container.py:314-355`) replaces it without calling `super()` and never sets `turn_extractor`.
- `write_memory` (`nodes/memory.py:225-241`) then gets `None` and skips `gather_turn_proposals` (`ze_memory/extractor.py:416`). No conversation turn has written memory events or entities since commit `4be61aa7` (2026-10-16).
- Key diff: only core sets `turn_extractor`. Every other core key is also set by ze-api. ze-api sets `fact_extractor=gather_fact_proposals` directly (`:322`).
- No test compares the two key sets. The nearest tests (`test_container_tier_judge.py`, `test_container_script_runner.py`) fill every container field with `MagicMock`, which would hide the gap.

### B4: the loop push bar's grounding and novelty never run (TRUE)

- **Grounding**: `AttentionArbitrationJob` calls `loop_surfacer.eligible_candidates(...)` with no NLI client (`ze_priority/arbitration.py:43`). `eligible_candidates` defaults `nli_client=None` (`ze_worldstate/surfacing.py:114`), `LoopSurfacer.__init__` (`:43-59`) has no NLI dependency, and `build_loop_surfacer` (`ze_worldstate/bootstrap.py:74-92`) builds it without one. `passes_grounding` passes when NLI is `None` (`ze_correlation/push.py:75`). The hypothesis source gets NLI through its builder (`wiring/container.py:556`), so `shared.nli_client` is available.
- **Novelty**: `passes_push_bar` reads `push_log.list_recent_payloads("worldstate_loop_push", 48)` (`surfacing.py:23`, `:87`). No production code writes that key.
- **What the governor records**: the notifier claims a discretionary push as a `push_log` row with `event_type='attention_push'` and `idempotency_key=budget_key` (`ze_proactive/attention_budget.py:41-58`, called at `notifier.py:149-150`). The claim is released on a failed persist or delivery (`notifier.py:189`, `:200`), so the surviving `attention_push` rows are exactly the discretionary pushes that ended `delivered` or `held`. Today the claim stores `payload=title`. For loops the title is always "Open loop" (`surfacing.py:150`), so the payload cannot serve novelty until it carries the body. No code reads the `attention_push` payload today.
- **New finding, out of scope**: `push_log`'s unique index `(event_type, idempotency_key)` (`zpro003`) has no window, and `push_log` is never pruned. With `budget_key = "loop:<id>"` (`surfacing.py:154`), a loop can be pushed at most once in its life. The user chose to leave this to phase 204 (clarify Q4); the Maestro adds it to 204's Context.

### B5: user pins are ignored outside REST and `TurnSurfacing` (TRUE; the effect is narrower than reported for composed answers and the briefing)

- `PriorityView` (`ze_priority/view.py`) never reads overrides. `rest.get_snapshot` (`rest.py:26-29`) and `TurnSurfacing._snapshot` (`turn.py:202-218`) each merge `override_store.get_active()` themselves. `TurnSurfacing` falls back to the computed order when the override read fails (`turn.py:216`).
- Consumers that read the computed order:
  - `reprioritize_item` resolves "more/less urgent" anchors against the computed `rank` (`tools.py:57`, `:95`). After the user moved an item, a second move picks the wrong anchor or answers "already at the top". **This is a real user-facing bug.**
  - `AttentionArbitrationJob` ranks push candidates with `rank_subset` (`arbitration.py:62`), unmerged.
  - `WorldComposer` (`compose/composer.py:93`) uses the ranking only for the relationship cards in "slipping" (`rules.py:273`) and for hypotheses in "topic" (`rules.py:565`, which re-sorts by match). Slipping loops and goals come from their stores by age, not from `PriorityView`.
  - The morning brief (`ze_personal/jobs/briefing.py:131`) orders at most three relationship nudges.
  - `submit_reprioritization` (`service.py:33`) needs the **computed** rank: the collision contribution states "position {item.rank}" (`contribution.py:39`).
- `PriorityOverride` (`types.py:92`) is anchor-relative: the item goes `above` or `below` an anchor, `pinned` or not. An unpinned override decays linearly to zero over 48 hours (`merge.py:9-20`).
- `PriorityView` is built once at `wiring/container.py:465`, and the override store exists before that line. The briefing receives the same instance.
- The governing rule is the `attention-arbitration.md` amendment of 2026-10-22: `PriorityView` returns the user's order by default; arbitration ranks candidates in the user's order; an item the user pushed down never wins a push; pins never add a push beyond the budget.

### B6: the compaction readout is shown on the wrong turns (PARTLY; the audit's framing is corrected)

- Graph order: `synthesize → record_trace → write_memory → END` (`ze_core/orchestration/graph.py:147-149`). `record_trace` reads `state["compaction_span"]` (`nodes/trace.py:79-84`). `write_memory` compacts after the reply and sets `compaction_span` to `(0, n-1)` (`memory.py:286`) or `None` (`:292`).
- The audit says the readout is "one turn late". Phase 112 defines it the other way. FR-011 there: "record, per turn, whether that turn's context included a compacted summary". Its acceptance scenario: "a turn whose prompt included a rolling summary". Turn N compacts after its reply, so N's prompt had no summary. Turn N+1's prompt is the first that has one, and today N+1 does show it.
- **The real bug**: only N+1 shows it. N+1's `write_memory` resets `compaction_span` to `None`, so turns N+2, N+3 … show no summary although their prompts still open with the summary message (`memory.py:342` marks it `compaction_summary`). A later re-compaction shows the same lag.
- `make_graph_input` (`ze_core/conversation/turn.py:32-90`) does not reset `compaction_span`. It also skips `loop_offer_ids`, `open_items_query`, `procedure_matches` and `resume_recap_applied`, but `fetch_context` rewrites those four every turn (`context.py:392-395`), and `pre_approved_writes` is a workflow input. Resetting `compaction_span` alone would hide compaction completely.
- Compaction code in `memory.py`: `43-45`, `252-265`, `267-294`, `308-317`, `320-342`. The provenance block that phase 199 edits is `199-223`.
- The web draws the readout at `apps/ze-web/src/widgets/assemble/ui/trace/instruments/readouts.ts:57`.

### B9: a workspace follow-up turn that parks a write is stuck (TRUE)

- `_ContainerTurnStarter.invoke_raw_turn` (`ze_api/wiring/container.py:154-168`) returns at `:161` when the outcome is interrupted.
- The WS path calls `send_confirmation_request` (`ws/turns.py:164-171`, `ws/confirmation.py:389-467`). It supersedes open rows, saves the pending row, sends `confirm_request`, sends the confirmation push and starts the timeout.
- The follow-up path (`ze_workspace` follow-through, `followthrough.py:215-225`) skips all five. The checkpoint stays paused with nothing that can answer it. Only the next user turn on that thread supersedes it.
- `handle_confirm` (`confirmation.py:124-129`) rebuilds the resume config from the stored row, so no per-socket state is needed.
- Phase 207 (spec line 25) names this as a stopgap for 198 and replaces it with the turn port.

### B10: a background thread waiting on a confirmation loses its rail dot (TRUE; it is a fixed-order overwrite, not a race)

Paths under `apps/ze-web/src`:

- The sessions rail draws the dot from `useWsStore` `thinkingThreads[id]` or `attentionThreads[id]` (`widgets/sessions-rail/ui/SessionsRail.tsx:32-34`).
- On `confirm_request`, `ConfirmationFrameHandler` sets thinking off and attention on for a thread that is not open (`features/respond-to-confirmation/ui/ConfirmationFrameHandler.tsx:16-19`).
- `TurnFrameHandler` then applies `{type: "paused"}` to the conversation reducer (`features/turn-stream/ui/TurnFrameHandler.tsx:95-99`). Its store sync (`:39-53`) copies the reducer's `attention` over the WS flag (`:49`).
- The reducer's `paused` case (`entities/conversation/model/reducer.ts:300-303`) never sets attention. Only an assistant `message` does (`:163`), and `opened` clears it (`:311-312`).
- `AppShell` mounts `ConfirmationFrameHandler` before `TurnFrameHandler` (`widgets/app-shell/ui/AppShell.tsx:119-120`), and frames dispatch in mount order (`shared/api/ws-client.ts:47-49`, `:215-231`). The dot is therefore lost every time. It is also lost when the client has never seen the thread, for example on replay after a reconnect.
- The server sends no `message` after a parking turn's `confirm_request`, so nothing sets the dot again.
- Phase 205 FR-004 makes this one reducer event and deletes the WS maps (FR-006). 198 does only the reducer half.

### B11: a failed push starts the job's cooldown (PARTLY)

- Four jobs read a cooldown, call `notify`, and then write the cooldown whatever the outcome:

  | Job | Read | Write |
  |---|---|---|
  | Morning brief | `ze_personal/jobs/briefing.py:69` (20 h) | `:119-125` |
  | Goal narrative | `ze_automation/jobs/goal_narrative.py:36` | `:87-93` |
  | Accountability | `ze_automation/jobs/accountability.py:44` | `:51-56` |
  | Workflow failure alert | `ze_automation/bootstrap.py:225` | `:239-246` |

- **Correction**: "or the budget suppressed it" is false for these jobs. All four push kinds are accountability-class (`ze_personal/push_kinds.py:5`, `ze_automation/push_kinds.py`), and the governor never budget-suppresses that class (`ze_proactive/governor.py:10-17`). The outcomes they can get are `delivered`, `held` and `failed`.
- **Trap**: the workflow-failure key `workflow_failure:<id>` is both the alert cooldown and the failure ledger. `list_workflow_failures_within_hours` reads `event_type LIKE 'workflow_failure:%'` (`push_log_store.py:96-102`) for `/status` and the briefing. Writing it only after a delivered push would hide failures from `/status`.
- **Correction, calendar**: the calendar reminder log (`ze_calendar/reminders/calendar.py:189`) is not a cooldown, and nothing reads it. The real calendar defect is different. `fire_reminder` marks the reminder sent before it calls `notify` (`:176`), so a `failed` push loses the reminder for good. `replay_unsent` (`:152`) only runs at startup, and it only fires unsent reminders.
- `notify(dedup_hours=…)` is unsuitable, as the brief says. `notification_store.exists_recent` (`notification_store.py:308-330`) has no delivery filter.

### B13: goals and workflows are registered twice for data portability (TRUE, and worse than reported)

- `automation_data_domains` registers `automation.goals` (`goals`) and `automation.workflows` (`workflows`) at delete order 10 (`ze_automation/bootstrap.py:84-140`).
- `PersonalPlugin.data_domains` registers `goals.goals` and `workflow.workflows` at order 30, with every goal and workflow child table at 19–20 (`ze_personal/plugin.py:127-212`).
- The container concatenates both lists without a duplicate check (`wiring/container.py:616-623`). No other table is registered twice.
- Effects (`ze_data/portability/service.py`, `assembler.py`):
  - Export writes both files, with the same rows.
  - Governance › Data lists both domains, with the same counts.
  - Import inserts twice. `ON CONFLICT DO NOTHING` (`assembler.py:85`) prevents duplicate rows, but `rows_imported` counts twice, and the web sums it (`Data.tsx:67`).
  - **Delete can fail.** Batches run in ascending order, and each batch runs in parallel (`service.py:165-175`). `DELETE FROM goals` (order 10) runs alongside `DELETE FROM open_loops` (also order 10), but `open_loops.goal_id REFERENCES goals(id)` has no `ON DELETE` clause (`zw001_open_loops.py:29`). Whether the delete hits a foreign-key violation depends on timing.

### B14: goal pause and abandon rules differ, and a finished goal can come back (TRUE)

- Goal statuses (`ze_automation/goals/types.py:35-41`): `planning`, `active`, `awaiting_gate`, `paused`, `completed`, `abandoned`.
- The WS screen actions (`ze_api/api/ws/goal_actions.py`):
  - pause (`:207-221`) requires `active` or `awaiting_gate`;
  - abandon (`:223-232`) refuses `completed` and `abandoned`.
- The agent tools (`ze_automation/agents/goals/tools.py`):
  - `pause_goal` (`:230-244`) checks only that the goal exists, and returns `undo_payload(goal_id)` with `undo_tool="resume_goal"`;
  - `abandon_goal` (`:323-332`) checks only existence;
  - `resume_goal` (`:255-271`) requires `paused`, sets `active` and starts `executor.advance`.
- `PostgresGoalStore.update_status` (`postgres.py:278-284`) is an unguarded `UPDATE`.
- **How a finished goal comes back**: the model pauses a completed or abandoned goal, and the tool sets `paused`. Then Retry's rollback (`base_agent.py:350-362`), or a plain "resume it" in chat, runs `resume_goal`, which sets `active` and calls `advance`. An abandoned goal with pending milestones starts executing again. A completed goal is marked completed a second time, and a second retrospective is pushed (`executor.py:249-256`).
- There are no REST pause or abandon routes.

### B15: Cancel never stops a running WS turn (TRUE; added by the user)

- The web sends `{"type": "command", "name": "cancel", "thread_id": …}` from `apps/ze-web/src/widgets/assemble/ui/RetryControl.tsx:31`. The WS handler calls `container.abort_invocation(thread_id)` (`ze_api/api/ws/commands.py:36-42`).
- `abort_invocation` (`ze_core/container.py:158-165`) looks the thread up in `_abort_tokens`. Only core `Container.invoke` fills that map (`:111-113`, popped at `:156`).
- WS turns, workspace follow-up turns and retries run through `invoke_raw_turn` (`ze_core/conversation/turn.py:261-274`, reached by `ZeContainer.invoke_raw_turn`, `wiring/container.py:362-371`, and by `invoke_retry_turn`, `turn.py:454-480`). It builds its config with no `abort_token` and registers nothing. A turn resumed after a confirmation runs through `resume_turn` (`turn.py:384`) with the same gap.
- So `abort_invocation` finds nothing, and the agentic loop's check (`ze_agents/base_agent.py:900-901`) never fires. The server still drops pending confirmations and sends `confirm_cancel`, so the client looks cancelled while the turn keeps running and later delivers its reply.
- `ZeContainer._build_config` passes extra keys through (`wiring/container.py:359`), so a token in `config_extra` reaches the nodes (`nodes/execution.py:302`) and the delegate (`ze_agents/delegate.py:280`).
- Phase 201 folds the token into the typed turn request.

## Clarifications

### Session 2026-10-22

Answers from the user, relayed by the Maestro.

- Q: B6, which turns show the compaction readout? → A: every turn whose prompt includes the summary (phase 112 FR-011), not the turn that compacted.
- Q: B11, what recovers a calendar reminder whose push failed? → A: clear its sent mark, so the next startup replay sends it as a late reminder. The record itself moves in phase 204 (FR-012).
- Q: B5, may an item the user pushed down still be pushed? → A: no. While the override is active, it is excluded from pushes, even when it is the only candidate.
- Q: The `push_log` lifetime idempotency index (a loop can be pushed once in its life): fix here or later? → A: leave it to phase 204. The Maestro adds it to 204's Context.
- Scope addition by the user: B15, Cancel never stops a running WS turn. `invoke_raw_turn` creates and registers the abort token; phase 201 later folds it into the turn request. Failing test first.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ze uses the user's timezone in every agent and every unattended run (Priority: P1)

The user lives in a configured timezone. Every agent that answers, including a specialist the companion delegates to, a subtask of a compound request, a goal milestone and a workflow step, knows the user's local date and time.

**Why this priority**: today every model call is told it is UTC. "Tomorrow morning" or "tonight" in any reply can be off by hours.

**Independent Test**: set the configured zone to `Europe/Lisbon`. Run a single-agent turn, a compound turn, a conductor delegation, a goal milestone and a workflow step. Assert that each agent context's zone is `Europe/Lisbon`.

**Acceptance Scenarios**:

1. **Given** the configured zone is `Europe/Lisbon`, **When** a turn routes to one specialist, **Then** that specialist's context zone is `Europe/Lisbon`.
2. **Given** the same configuration, **When** a compound turn runs two subtasks, **Then** both subtask contexts carry `Europe/Lisbon`.
3. **Given** the same configuration, **When** the companion delegates to a specialist, **Then** the delegate's context carries `Europe/Lisbon`.
4. **Given** the same configuration, **When** a goal milestone or a workflow step runs unattended, **Then** its agent context carries `Europe/Lisbon`.
5. **Given** no zone is configured, **When** any of the above runs, **Then** the zone is UTC, as today.

---

### User Story 2 - Conversation turns feed the memory graph again (Priority: P1)

What the user says in conversation produces memory events and entities, as it did before 2026-10-16.

**Why this priority**: this is silent data loss. Every turn since then has dropped its events and entities, and entity-anchored retrieval and the Mind graph decay without them.

**Independent Test**: build the application container and its turn configuration, and assert that the turn extractor is present. A second test asserts that every key the core container's configuration provides is also provided by the application container's.

**Acceptance Scenarios**:

1. **Given** the application container, **When** it builds a turn's configuration, **Then** the turn extractor is the production extractor.
2. **Given** a future key added to the core container's configuration, **When** the application container does not provide it, **Then** a test fails and names the missing key.

---

### User Story 3 - A write parked by a workspace follow-up reaches the user (Priority: P1)

A detached workspace run finishes, and Ze's automatic follow-up turn wants to do something that asks first. The user gets the confirmation card (or a push when offline) and can approve or deny it, exactly as in a normal turn.

**Why this priority**: today the thread is left paused with nothing on screen that can answer it.

**Independent Test**: drive the follow-up turn starter with an interrupted outcome that holds one parked write. Assert one `confirm_request` frame on the thread, one saved pending row, one confirmation push and a started timeout.

**Acceptance Scenarios**:

1. **Given** the user is connected, **When** a follow-up turn parks a write, **Then** the thread shows the confirmation card.
2. **Given** the user is offline, **When** a follow-up turn parks a write, **Then** a confirmation push is sent, and the card appears on reconnect.
3. **Given** the user never answers, **When** the confirmation timeout passes, **Then** the turn resumes as a timeout and replies "Okay, I didn't …".

---

### User Story 4 - A finished goal stays finished (Priority: P1)

Pause, abandon and resume follow one rule set, whether the user acts on the goal's screen or asks in chat. A completed or abandoned goal cannot be paused, and so it can never be resumed back to life.

**Why this priority**: today a chat "pause" then "resume", or a Retry, can restart an abandoned goal or push a second retrospective for a completed one.

**Independent Test**: a table test over all six statuses. Call the pause and abandon tools and the matching screen actions, and assert that they allow and refuse the same statuses. A refused tool call changes nothing and offers no undo.

**Acceptance Scenarios**:

1. **Given** a completed goal, **When** the model calls `pause_goal`, **Then** the tool returns an error, the status is unchanged, and the result carries no undo payload.
2. **Given** an abandoned goal, **When** the model calls `abandon_goal`, **Then** the tool returns an error and changes nothing.
3. **Given** an active goal, **When** it is paused and the pause is rolled back by Retry, **Then** it is active again, as today.
4. **Given** any status, **When** the screen action and the tool act on it, **Then** both allow or both refuse.

---

### User Story 5 - The user's priority order is the order Ze acts on (Priority: P2)

When the user drags an item above another, or tells Ze "this is more urgent", every part of Ze that ranks open items uses that order: the "what's open" answers, composed answers, the next "more/less urgent" move, which drifting item wins the next push, and the morning brief.

**Why this priority**: the user's explicit choice is ignored by most consumers, and a second "more urgent" move can pick the wrong anchor.

**Independent Test**: a fake override store places item B above item A, where A has the higher computed rank. Assert that `PriorityView` returns B first. Assert that arbitration sends B first, and that a "more urgent" move on B answers that B is already at the top.

**Acceptance Scenarios**:

1. **Given** the user pinned B above A, **When** any consumer asks for the ranking, **Then** B comes before A.
2. **Given** the user moved B to the top, **When** they say "make B more urgent", **Then** Ze says B is already the most urgent and records nothing.
3. **Given** two drifting loops are push candidates and the user ranked the lower-scored one first, **When** arbitration runs with one push left, **Then** the user's first choice is sent.
4. **Given** the user pushed an item down, **When** it is the only other push candidate, **Then** it is not pushed.
5. **Given** the user has pins and the daily budget is spent, **When** arbitration runs, **Then** nothing is pushed.
6. **Given** the override store cannot be read, **When** a consumer asks for the ranking, **Then** it gets the computed order and a warning is logged.
7. **Given** the user reorders, **When** the reorder is checked for a collision with Ze's own order, **Then** the collision record still compares against the computed rank.

---

### User Story 6 - A loop push is grounded and not a repeat (Priority: P2)

Ze pushes about a drifting loop only when its evidence supports the loop's title, and not when it just pushed something nearly identical.

**Why this priority**: both checks exist but are switched off by wiring, so unsupported or repeated loop pushes can reach the user's phone.

**Independent Test**: run `AttentionArbitrationJob.run` with a real `LoopSurfacer` built the way the application builds it. One drifting loop's title is not supported by its evidence, and another's rationale nearly repeats a push the governor recorded in the last 48 hours. Neither is pushed.

**Acceptance Scenarios**:

1. **Given** a drifting loop whose evidence does not support its title, **When** arbitration runs, **Then** the loop is not pushed.
2. **Given** Ze pushed a near-identical message 3 hours ago, **When** arbitration runs, **Then** the loop is not pushed.
3. **Given** a push 3 hours ago that failed to deliver, **When** arbitration runs, **Then** that push does not count against novelty.

---

### User Story 7 - A failed push is tried again (Priority: P2)

A morning brief, weekly goal narrative, accountability summary or workflow-failure alert that failed to send is sent on the job's next run, and it is not blocked for the whole cooldown window.

**Why this priority**: today one ntfy outage at 07:00 cancels that day's brief.

**Independent Test**: for each of the four jobs, run it with a notifier that returns `failed`, then with one that returns `delivered`. Assert one delivery, and no cooldown written after the failure. `held` starts the cooldown, as `delivered` does.

**Acceptance Scenarios**:

1. **Given** the morning brief push failed at 07:00, **When** the job runs again, **Then** the brief is sent.
2. **Given** the brief was delivered, or held for quiet hours, **When** the job runs again inside the window, **Then** no second brief is sent.
3. **Given** a workflow failed and its alert push failed, **When** the user opens `/status`, **Then** the failure is listed, and the next failure of that workflow alerts again.
4. **Given** a calendar reminder whose push failed, **When** the server next starts, **Then** the reminder is sent as a late reminder.

---

### User Story 8 - The compaction readout matches what the model saw (Priority: P3)

The trace of every turn whose prompt opened with a compacted summary says so, and says which messages the summary covers.

**Why this priority**: it is a transparency readout. The conversation works without it, but today it appears on one turn and then disappears while the summary is still in use.

**Independent Test**: a graph-level test runs four turns on one thread with a history long enough to compact after turn 1. Assert the compaction readout on each turn according to FR-021.

**Acceptance Scenarios**:

1. **Given** a thread whose history was compacted after turn N, **When** the user inspects the traces of turns N+1, N+2 and N+3, **Then** each shows the summary and the span it covers.
2. **Given** the same thread, **When** the user inspects turn N, **Then** it shows no summary, because its prompt had none.
3. **Given** a thread that has never compacted, **When** the user inspects any trace, **Then** no compaction is shown.
4. **Given** a thread compacted a second time after turn M, **When** the user inspects turn M+1, **Then** it shows the newer summary's span.

---

### User Story 9 - A confirmation on another thread keeps its dot (Priority: P3)

The user is on one thread while Ze works on another, and that other turn asks for a confirmation. The sessions rail keeps a dot on the waiting thread until the user opens it.

**Why this priority**: the confirmation card and push still exist, but in the web app nothing in the rail shows which thread is waiting.

**Independent Test**: render the confirmation and turn frame handlers in the shell's order. Feed `typing` and then `confirm_request` for a thread that is not open. Assert attention on, thinking off, and the card stored. Open the thread, and assert attention off.

**Acceptance Scenarios**:

1. **Given** thread T2 is running in the background, **When** its `confirm_request` arrives, **Then** T2 shows the attention dot.
2. **Given** the client has never seen T2 (a replay after reconnect), **When** T2's `confirm_request` arrives, **Then** T2 shows the attention dot.
3. **Given** T2 shows the dot, **When** the user opens T2, **Then** the dot clears.
4. **Given** the open thread receives a `confirm_request`, **When** it arrives, **Then** no attention dot is set for it.

---

### User Story 10 - Export, import and delete see each table once (Priority: P3)

Governance › Data counts goals and workflows once, an export holds one copy of them, an import reports the true row count, and "delete my data" never fails on the goals table.

**Why this priority**: the delete failure is real but timing-dependent. The double counts are cosmetic.

**Independent Test**: build the data domains exactly as the application does. Assert that every table is registered once, and that goals are deleted in a later batch than open loops.

**Acceptance Scenarios**:

1. **Given** the full domain list, **When** an export runs, **Then** each table is selected once.
2. **Given** a database with goals linked to open loops, **When** "delete my data" runs, **Then** open loops are deleted before goals, and no foreign-key error occurs.

---

### User Story 11 - Cancel stops the turn (Priority: P2)

The user presses Cancel while Ze is working on a reply. The running turn stops at its next check, and no late reply arrives afterwards.

**Why this priority**: today Cancel looks like it worked, but the turn keeps running, its tools keep acting, and its reply arrives later.

**Independent Test**: start a turn through the turn entry point with a graph that waits inside a node, call the container's abort for that thread, and assert that the token the node received is set. A second case does the same for a turn resumed after a confirmation.

**Acceptance Scenarios**:

1. **Given** a turn is running on thread T, **When** the user presses Cancel, **Then** the token the turn's agents see is set, and the agentic loop stops at its next check.
2. **Given** a turn resumed after the user approved a confirmation, **When** the user presses Cancel, **Then** that turn stops too.
3. **Given** a turn on thread T has finished, **When** a new turn starts on T, **Then** an old Cancel cannot stop it, and the finished turn's token is no longer registered.
4. **Given** turns running on threads T1 and T2, **When** the user cancels T1, **Then** T2 is not affected.

### Edge Cases

- A configured zone that is not a valid IANA name. The agent context falls back to UTC with one warning, as `CalendarReminderService._user_tz` already does.
- The companion delegates to a specialist from inside a compound subtask. The delegate inherits the subtask's zone.
- A follow-up turn parks a write while the user already has an open confirmation on that thread. The older one is superseded, as on the WS path.
- A follow-up turn's parked write is the fourth confirmation round. It is refused over the cap, as on the WS path.
- `awaiting_gate` → pause → Retry rollback gives `active`, and `advance` re-checks the open gate. This is accepted for 198; phase 211 owns the full lifecycle.
- An override whose anchor is no longer ranked (the anchor closed). The merge already handles this; the item keeps its computed place.
- An override that has decayed to zero weight does not push an item down.
- A push candidate the user pinned while the budget is exhausted. It is not pushed (the budget wins).
- The notifier holds a loop push for quiet hours. The held push counts for novelty.
- Two workflow failures within the alert cooldown. Both are listed in `/status`, and one alert is sent.
- A thread is compacted twice. The readout shows the newest summary's span.
- Cancel arrives after the turn finished. It is a no-op, as today.
- Two turns overlap on one thread (the thread lock normally prevents it). A turn removes only its own token from the registry, never a newer one.
- An archive exported before this phase that still holds the duplicate files. Import reads only registered domains, so the extra file is ignored.

## Requirements *(mandatory)*

### Functional Requirements

**Timezone (B1)**

- **FR-001**: The application settings MUST expose the user's timezone, resolved from the YAML `timezone` key, then the `TIMEZONE` environment variable, then UTC. The engine settings conversion MUST use the same value.
- **FR-002**: Every agent context built for a subtask, a compound subtask or a delegated specialist MUST carry the parent context's timezone.
- **FR-003**: Goal milestone contexts MUST carry the configured timezone. The goal executor receives it by constructor injection.
- **FR-004**: An invalid zone name MUST fall back to UTC with a warning, and never fail a turn.

**Turn configuration (B2)**

- **FR-005**: The application container's turn configuration MUST provide the production turn extractor.
- **FR-006**: A test MUST fail when a key set by the core container's turn configuration is missing from the application container's. Phase 201 replaces this guard with typed turn services.

**Workspace follow-up confirmations (B9)**

- **FR-007**: When a workspace follow-up turn ends interrupted on a write confirmation, the system MUST do what the WS turn path does: supersede open requests on the thread, save the pending row, send `confirm_request`, send the confirmation push, and start the timeout. It MUST reuse the existing confirmation request function. It MUST NOT add a second implementation. Phase 207 replaces this call with the turn port.

**Goal lifecycle (B14)**

- **FR-008**: One set of pure precondition rules MUST decide whether a goal may be paused (from `active` or `awaiting_gate`), abandoned (from `planning`, `active`, `awaiting_gate` or `paused`) or resumed (from `paused`). It lives in ze-automation's goals module and is exported there.
- **FR-009**: The `pause_goal` and `abandon_goal` tools and the WS screen actions MUST apply those rules. A refused tool call MUST return an error, change nothing, and carry no undo payload. `resume_goal` keeps its rule, now read from the same place.

**Priority order (B5)**

- **FR-010**: `PriorityView` MUST own the override store, by constructor injection, and return items in the user's order by default. Each item MUST keep its computed rank as a separate field.
- **FR-011**: If the override store cannot be read, `PriorityView` MUST return the computed order and log a warning.
- **FR-012**: The REST snapshot and `TurnSurfacing` MUST stop merging overrides themselves (hard cut). `reprioritize_item` MUST resolve its anchors against the user's order.
- **FR-013**: The collision record for a reprioritization MUST compare against the computed rank.
- **FR-014**: Push arbitration MUST order candidates by their place in the user's full order, MUST never push a candidate the user pushed down, and MUST NOT push beyond the daily budget. "Pushed down" means an active override (pinned, or unpinned with weight above zero) that places the item lower than its computed rank. A pushed-down item is excluded from pushes while its override is active, even when it is the only candidate.

**Loop push bar (B4)**

- **FR-015**: `LoopSurfacer` MUST receive the NLI client by constructor injection, from the same shared client the hypothesis source uses. The per-call NLI parameter MUST be removed (hard cut).
- **FR-016**: The governor's claim for a discretionary push MUST record the pushed body, not the title.
- **FR-017**: Loop novelty MUST compare the candidate's push text against the bodies of discretionary pushes the governor recorded in the last 48 hours. The `worldstate_loop_push` key MUST be removed. Phase 204 replaces this with the push-bar module.

**Cooldowns (B11)**

- **FR-018**: The morning brief, goal narrative, accountability and workflow-failure alert jobs MUST start their cooldown only when the push outcome is `delivered` or `held`. They MUST NOT use `notify(dedup_hours=…)`.
- **FR-019**: A workflow failure MUST still be recorded for `/status` and the briefing whatever the alert's outcome. The alert cooldown MUST be recorded apart from the failure ledger.
- **FR-020**: A calendar reminder whose push fails MUST be marked unsent again, so the next startup replay sends it as a late reminder.

**Compaction readout (B6)**

- **FR-021**: The trace MUST show the compaction span on every turn whose prompt opens with a compacted summary, and on no other turn. It is derived from the history the turn actually sent to the model, not from a flag set after the reply. The `compaction_span` state field MUST be removed (hard cut). Phase 199's lines in `nodes/memory.py` (199-223) MUST stay untouched.

**Rail attention (B10)**

- **FR-022**: A `confirm_request` for a thread that is not open MUST leave that thread's attention dot on, whether or not the client knew the thread, until the user opens it. The conversation reducer MUST be the only writer of that flag on this path.

**Data portability (B13)**

- **FR-023**: Each table MUST be registered for data portability exactly once. The ze-automation goal and workflow domains MUST be removed; ze-personal keeps the full, ordered goal and workflow set until phase 211 or 217 moves it.
- **FR-024**: A test MUST fail when two registered domains name the same table, and MUST check that goals are deleted after open loops.

**Cancel (B15)**

- **FR-027**: Every turn started through the raw turn entry point, and every resumed turn, MUST create an abort token, register it under its thread for the length of the turn, and pass it to the graph, so that the container's abort for that thread stops the turn's agentic loop. The registration MUST be removed when the turn ends, and only if it is still that turn's token. Phase 201 folds the token into the typed turn request.

**Cross-cutting**

- **FR-025**: Each fix MUST start with a failing test through the real interface named in its user story.
- **FR-026**: No migration. No REST or WS shape change. `PriorityItem` gains its computed rank internally; the REST snapshot already carries `displayed_rank` and `computed_rank`.

### Key Entities

- **Agent context timezone**: the user's IANA zone, carried by every agent context that builds a prompt.
- **Priority item**: an open item in the user's order, with its displayed rank and its computed rank.
- **Goal lifecycle rule**: which statuses allow pause, abandon and resume.
- **Discretionary push record**: the governor's claim row for a push that ended `delivered` or `held`, now holding the pushed body.
- **Job cooldown record**: a push-log entry a job writes only after a delivered or held push.
- **Workflow failure record**: the push-log ledger row `/status` reads, written for every failure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of agent contexts that build a prompt carry the configured zone, across single, compound, delegated, milestone and workflow paths. Each path has a test that fails today.
- **SC-002**: A conversation turn with extractable events produces memory events and entities again. A container test proves the extractor is wired, and a key-diff test guards the two configurations.
- **SC-003**: A follow-up turn that parks a write produces exactly one confirmation card, one pending row and one push.
- **SC-004**: Zero goal statuses on which the screen action and the tool disagree, across all six statuses.
- **SC-005**: Every consumer of the priority ranking returns the user's order. The view, `reprioritize_item`, push arbitration and composed answers each have a test that fails today; REST, `TurnSurfacing` and the morning brief read the same view instance.
- **SC-006**: An ungrounded or repeated loop candidate is rejected in a test through `AttentionArbitrationJob.run`, with no direct call to a bar function.
- **SC-007**: For each of the four jobs, a failed push never starts a cooldown. One parametrized test per job proves it.
- **SC-008**: The compaction readout is correct on 4 consecutive turns of a graph-level test.
- **SC-009**: The rail dot survives a background `confirm_request` in a test that renders both frame handlers in the shell's order.
- **SC-010**: Each table appears once in the registered data domains.
- **SC-011**: Cancel stops a running turn and a resumed turn in a test through the turn entry points; a finished turn leaves no token registered.
- **SC-012**: `make test-py`, `make test-web`, `make typecheck-web` and `make lint` pass.

## Assumptions

- Phases 200, 201, 204, 205, 207, 211 and 217 replace these fixes with deeper modules. 198 adds no module that a later phase must delete, except the key-diff guard (FR-006), which 201 removes, the follow-up confirmation call (FR-007), which 207 replaces, and the turn-level abort registration (FR-027), which 201 folds into the turn request.
- Phase 199 runs in parallel on its own floor and edits `nodes/memory.py` lines 199-223. 198 edits only the compaction lines (252-342).
- The new `push_log` lifetime-idempotency finding (a loop can be pushed once in its life) is reported to phase 204 and is not fixed here.
- Thresholds, windows and push kinds keep their current values.
- Dev data is disposable (`pre-v1-hard-cuts.md`). No data repair is needed, because nothing was stored wrongly that a later read depends on. Memory events and entities lost since 2026-10-16 are not recovered.
