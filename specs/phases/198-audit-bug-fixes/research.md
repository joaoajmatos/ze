# Research: Audit Bug Fixes

Decisions per bug. Evidence (file:line) is in the spec's Context section. Each entry: **Decision**, **Rationale**, **Alternatives rejected**.

## B1 — timezone

- **Decision**: add a `timezone` property to `ZeApiSettings` that resolves the YAML `timezone` key, then `TIMEZONE`, then `"UTC"`; `to_core_settings()` uses it. Pass `timezone=base_ctx.timezone` at `execution.py:388` and `:493`, and `timezone=ctx.timezone` at `delegate.py:270`. `GoalExecutor.__init__` gains `timezone: str = "UTC"`, used at `executor.py:906` and supplied from `settings.timezone` at `ze_automation/bootstrap.py:164`. An invalid zone name falls back to UTC with one warning, at the place the prompt is built (`BaseAgent._build_system_prompt` already formats the zone; the check uses `zoneinfo.ZoneInfo`, as `CalendarReminderService._user_tz` does).
- **Rationale**: fixing only the two subtask sites (the audit's claim) would copy a UTC parent. The root is that `fetch_context` reads `settings.timezone` and the application settings have none. Workflows already go through `fetch_context`, so the settings fix covers them.
- **Rejected**: deriving every child context from its parent with one function. That is phase 200 (agent context derivation) and would replace the hand copies; 198 only adds the missing field.

## B2 — turn extractor

- **Decision**: add `"turn_extractor": gather_turn_proposals` to `ZeContainer._build_config`, next to `fact_extractor` (`wiring/container.py:322`). New test `apps/ze-api/tests/test_container_config.py` builds a `ZeContainer` with the real `_build_config` and asserts (1) `turn_extractor is gather_turn_proposals`, and (2) `set(Container._build_config(c, "t1")["configurable"]) <= set(ZeContainer._build_config(c, "t1")["configurable"])`, naming any missing key.
- **Rationale**: the smallest change that restores the behaviour, plus a guard that would have caught the regression.
- **Rejected**: starting from `super()._build_config()`. It removes the duplication but changes every key's source; phase 201 replaces the string bag with typed turn services anyway.

## B4 — loop push bar

- **Decision**:
  1. `LoopSurfacer.__init__(…, nli_client)` and `build_loop_surfacer(…, nli_client)` take NLI; `wiring/container.py:532` passes `shared.nli_client`. The `nli_client` parameter of `passes_push_bar` and `eligible_candidates` is removed.
  2. The notifier's discretionary claim stores `payload=body` instead of `payload=title` (`notifier.py:150`).
  3. `LoopSurfacer.passes_push_bar` compares `format_hedged_mention(loop.title, rationale)` (the text it would push) against `push_log.list_recent_payloads(ATTENTION_PUSH_EVENT_KEY, 48)`. `PUSH_EVENT_KEY = "worldstate_loop_push"` is deleted.
- **Rationale**: the brief asks novelty to read "what the governor records". The governor's `attention_push` rows exist only for pushes that ended `delivered` or `held` (claims are released on failure, `notifier.py:189`, `:200`), which is the right history. Today the payload is the title, and every loop push's title is "Open loop", so the body must be recorded. Nothing reads that payload today. Comparing the pushed text with pushed bodies keeps the comparison like-for-like.
- **Rejected**: having `LoopSurfacer.send` write the old `worldstate_loop_push` key after a delivered push. It is smaller but keeps a per-source key that phase 204 FR-002 forbids, and it ignores hypotheses' pushes.
- **Out of scope (user's answer to Q4)**: the `push_log` unique index has no window, so `loop:<id>` can be claimed once per loop lifetime. Phase 204 owns it; the Maestro adds it to 204's Context.

## B5 — the user's order

- **Decision**:
  - `PriorityView.__init__` gains `override_store` and `clock` (constructor injection; `wiring/container.py:465` passes `stores.priority_override_store`).
  - `rank()` reads `get_active()`, applies `merge` and returns items in the user's order with `rank` = displayed rank. `PriorityItem` gains `computed_rank: int` and `override: PriorityOverride | None`.
  - On an override read failure, `rank()` logs `priority_overrides_unavailable` and returns the computed order, as `TurnSurfacing` does today (`turn.py:216`).
  - `rest.get_snapshot` and `TurnSurfacing._snapshot` stop calling `merge` and `get_active`; `TurnSurfacing` loses its `override_store` dependency. `MergedPriorityItem` is built from the item's fields.
  - `reprioritize_item._resolve_anchor` sorts by the displayed rank.
  - `synthesized_claim_contribution` (`contribution.py:39`) reads `item.computed_rank`.
  - `rank_subset` (arbitration) orders candidates by their position in the full `rank()`, and drops a candidate whose item is pushed down (active override, weight > 0, displayed rank greater than computed rank). Budget rules are unchanged (`arbitration.py:39` and the governor claim).
  - The composer and the briefing need no code change; they receive the shared `PriorityView`.
- **Rationale**: the amendment to `attention-arbitration.md` (2026-10-22) puts the merge inside `PriorityView`. Keeping the computed rank on each item lets the collision log compare against Ze's own order without a second public method.
- **Rejected**: a separately named `user_order()` method next to `rank()`. Every consumer would have to remember to call it, which is the shallow seam that caused B5.
- **User's answer (Q3)**: a pushed-down item is excluded from pushes while its override is active, even when it is the only candidate.

## B6 — compacted summary and readout

- **Decision (user's answers to Q1 and Q5)**:
  1. Keep the summary. `write_memory`'s non-compacting branch (`memory.py:290-294`) keeps a leading message that carries `compaction_summary`: the stored history is `[summary] + updated[-SESSION_HISTORY_LIMIT:]`. A history that does not open with a summary is trimmed as today. Re-compaction needs no change: `older_span = updated[:-SESSION_HISTORY_LIMIT]` starts with the old summary and `_format_transcript` renders it as `system: <summary>`, so the new summary folds it in and the history holds one summary at a time. When `_compact` fails it returns `None` and the turn falls through to the same branch, so an earlier summary stays in front.
  2. Derive the readout. `_compact` records the folded span on the summary message it creates (`{"role": …, "content": …, "compaction_summary": True, "compaction_span": [0, k]}`, `memory.py:320-342`). `record_trace` derives `MessageTrace.compaction` from the first message of the history the turn was sent with: if it carries `compaction_summary`, the readout is its span; otherwise `None`. `write_memory` stops returning `compaction_span` (`memory.py:286`, `:292`), and the `AgentState.compaction_span` field is removed.
- **Rationale**: the engine lane's four-turn graph test showed the summary in the prompt on turns `[no, yes, no, no]`: the trim at `memory.py:291` drops it one turn after it is made, so phase 112's rolling summary (FR-002, FR-004) lasted one turn and the readout was already "correct" for that one turn. Keeping the summary fixes the continuity 112 promised, and the readout then follows from the history, as phase 112 FR-011 defines it ("this turn's context included a compacted summary"). The cost is one system message (the summary) in every prompt after a compaction, until the next compaction replaces it.
- **Rejected**: (Q5 B) keeping the trim and only deleting the state field; it leaves 112's summary one turn long. Stamping the span on the turn that compacted, by patching `message_trace` in `write_memory`; that reports a summary the turn's prompt did not contain. Adding `compaction_span` to `make_graph_input`'s reset; it would hide compaction on every turn because `record_trace` runs before `write_memory`.
- **Coordination**: the edits stay in `memory.py` 252-342; phase 199 owns 199-223.

## B9 — follow-up confirmation

- **Decision**: in `_ContainerTurnStarter.invoke_raw_turn` (`wiring/container.py:161`), when `outcome.interrupted`, call `send_confirmation_request(container.connection_manager, container, outcome, thread_id, confirmation_store=container.confirmation_store)` and return. Import it inside the method. Drop the returned `(request_id, config)`; `handle_confirm` rebuilds the config from the stored row.
- **Rationale**: it reuses the WS path's one function, so supersede, row, frame, push and timeout behave the same. Phase 207 replaces the call with the turn port.
- **Rejected**: duplicating the frame and row writes in the starter.

## B10 — rail dot

- **Decision**: in `reducer.ts`, `paused` sets `attention: t.attention || threadId !== ctx.activeThreadId`, and moves `phase` to `paused` only when the thread is running (as today). Delete the two `useWsStore` setters (`setThreadThinking`, `setThreadAttention`) from `ConfirmationFrameHandler.tsx`. Update the reason text for `confirm_request` in `frame-registry.ts:73`.
- **Rationale**: one writer for the flag. The sync in `TurnFrameHandler` then writes thinking off and attention on from the reducer. This is phase 205 FR-004 without 205's selectors.
- **Rejected**: swapping the mount order in `AppShell`; it keeps two writers.

## B11 — cooldowns

- **Decision**:
  - Morning brief, goal narrative and accountability: `outcome = await notifier.notify(...)`, then `push_log.log(...)` only when `outcome in ("delivered", "held")`, an inline check like `arbitration.py:77`.
  - Workflow failure (`ze_automation/bootstrap.py:225-246`): the ledger row `workflow_failure:<id>` is written for every failure (unchanged, so `/status` and the briefing keep listing every failure). The alert cooldown moves to a new key `workflow_failure_alert:<id>`, read by `was_sent_within_hours` and written only after `delivered` or `held`. `LIKE 'workflow_failure:%'` does not match the new key.
  - Calendar (user's answer to Q2): when `notify` returns `failed`, `CalendarReminderStore.mark_unsent(reminder_id)` resets `sent`, so the next startup `replay_unsent` fires it as a late reminder. The dead `calendar_reminder:<id>` push-log write is left for 204 FR-012.
- **Rationale**: the four jobs get only `delivered`, `held` or `failed` (accountability class). Splitting the workflow key avoids hiding failures from `/status`.
- **Rejected**: `notify(dedup_hours=…)` (matches any outcome); the shared outcome predicate (phase 204 FR-014).

## B13 — duplicate data domains

- **Decision**: delete the `automation.goals` and `automation.workflows` entries from `automation_data_domains` (`ze_automation/bootstrap.py:84-140`); keep `automation.accountability`. New test `apps/ze-api/tests/test_data_domains_unique.py` builds the same list the container builds, over a fake pool, and asserts that each table appears once and that `DELETE FROM goals` runs in a later batch than `DELETE FROM open_loops`.
- **Rationale**: ze-personal's set is complete and correctly ordered (goals at 30, after loops at 10). Removing ze-personal's copy instead would leave goals at order 10, beside `open_loops`, and keep the foreign-key race.
- **Rejected**: the table-domain factory (phase 217, which also takes over the uniqueness test).

## B14 — goal lifecycle

- **Decision**: new `ze_automation/goals/lifecycle.py` with `can_pause(status)`, `can_abandon(status)`, `can_resume(status)` (pure, over `GoalStatus`), exported from `ze_automation.goals`. `pause_goal` and `abandon_goal` check them before writing and return `{"error": "<goal> is <status>; it cannot be paused/abandoned."}` without an undo payload; `resume_goal` reads `can_resume`. `goal_actions.py` uses the same functions in place of its inline checks, keeping its "Goal already resolved." line.
- **Rationale**: one rule set in the package that owns goals. Phase 211 grows the same module into the full lifecycle. `GoalStore.update_status` stays unguarded because the executor uses it internally at about ten sites.
- **Rejected**: guarding `update_status` in the store.

## B15 — Cancel

- **Decision**: a small helper in `ze_core/conversation/turn.py` creates an `AbortToken`, stores it in `container._abort_tokens[thread_id]` (read with `getattr`, so a container without the registry still runs), and removes it in a `finally` only when the stored token is still this one. `invoke_raw_turn` passes it as `config_extra["abort_token"]` to `_build_config`. `resume_turn` receives a built config from its caller, so it adds the token to `config["configurable"]` before `ainvoke`. `invoke_retry_turn` goes through `invoke_raw_turn` and needs nothing else. The WS `cancel` command already calls `abort_invocation`; it does not change.
- **Rationale**: the map and `abort_invocation` already exist on the core container, and the nodes and the delegate already forward `configurable["abort_token"]` to the agentic loop. Only the registration is missing on the turn path. The identity check on removal keeps an overlapping or later turn's token in place.
- **Rejected**: moving token ownership into the WS handler. Workspace follow-ups and retries would miss it; phase 201 makes it part of the typed turn request.
