# Tasks: Retry Rollback

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Mock asyncpg pools; never call OpenRouter or System One. Web tests with vitest.

**Lanes**: `[ENG]` = Claude Sonnet lane lead (cross-package design, concurrency, integration, gates). `[JR]` = OpenCode flash junior (exact files and behavior given). See the Lanes section at the end. Each task ends with `· <files it may touch>`.

**Tags**: `[BE]` backend Python · `[WEB]` ze-web and generated client · `[PLATFORM]` migrations, codegen, eval · `[DOCS]` docs, READMEs, specs. `[P]` = parallelizable (different files). `[US#]` = user story in spec.md.

**DOCS rule (user)**: [DOCS] tasks cover every public doc the phase changes (root `README.md`, `docs/*.md`, package READMEs), not only `AGENTS.md` and the specs index, and end with a coverage check against `git diff main...HEAD`. Follow `.claude/skills/doc-style/SKILL.md` for public docs (not for `specs/` or `AGENTS.md`).

**Rules for the implementer**
- Before changing any signature in the plan's Package ownership table, run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep -rn "<name>" --include='*.py' .` (graphify misses `ze_sdk` re-exports), and update every caller in the same change.
- Plugins import from `ze_sdk.*` only. `ze-agents` imports neither `ze_memory` nor `ze_core`.
- No `print()`; `get_logger(__name__)`. No bare `Exception` / `ValueError` in domain code; new errors subclass `ZeError`.
- Pre-v1 hard cut: no backfill of undo payloads, no second retry mode, delete removed reason codes (no aliases).
- `make lint` before handing a task back. Do not commit unless asked. If a step disagrees with the code you find, stop and report the difference; do not redesign.

---

## Phase 0: Gate  [ENG]

- [x] **T001** [ENG] [BE] Baseline. Run `graphify update .`, then `graphify affected` for `ToolCall`, `ToolCallTrace`, `MessageTrace`, `retry_eligibility`, `RetryReason`, `invoke_retry_turn`, `handle_retry`, `BaseAgent.call_tool`, `submit_reprioritization`, `PriorityOverrideStore.create`, `_write_fact_with_contradiction_check`, `submit_perception_facts`, `forget_fact`. Write the caller list (by package) into your first report. Run `make test-agents test-core test-api` and record the baseline. · none

---

## Phase 1: Foundation (blocks every story)  [ENG]

**Purpose**: payload contract, rollback scope, trace fields, storage. No user-visible change. When T007 lands, post "foundation landed" to JR-A and JR-B in the Handoffs note.

- [x] **T002** [ENG] [BE] `ze-agents`: `undo_payload(**kwargs) -> dict` in `tool.py`; values must be `str | int | float | bool | None` or lists of those, else `AgentConfigError`. Tests. · `core/contracts/ze-agents/ze_agents/tool.py`, `core/contracts/ze-agents/tests/test_tool_undo_payload.py`
- [x] **T003** [ENG] [BE] `ze-agents`: `ToolCall.agent: str | None = None`, `ToolCall.undo: dict | None = None` (`types.py`). New `rollback.py`: `RollbackScope(retried_message_id: UUID)` frozen dataclass, ContextVar, `rollback_scope(scope)` context manager, `current_rollback_scope()`, `is_error_result(result) -> bool` (dict with `error` key, `ok is False`, or `status == "error"`). Export from `ze_agents/__init__.py`. Tests. · `core/contracts/ze-agents/ze_agents/{types.py,rollback.py,__init__.py}`, `core/contracts/ze-agents/tests/test_rollback_scope.py`
- [x] **T004** [ENG] [BE] [US1] [US3] `BaseAgent.call_tool`: set `agent=self.name` on every returned `ToolCall`; for a successful dict result of a REVERSIBLE tool, pop `"undo"` into `ToolCall.undo`; drop and log `"undo"` from any other tool or failed call. Retry rule (FR-019): under `ctx.retry_mode` refuse only `spec.reversibility is ToolReversibility.IRREVERSIBLE` (same `RETRY_WRITE_REFUSAL`, `gate="denied"`); REVERSIBLE runs. Update the 165 tests that assert every write is refused. · `core/contracts/ze-agents/ze_agents/base_agent.py`, `core/contracts/ze-agents/tests/test_call_tool_undo.py`, `core/engine/ze-core/tests/orchestration/test_retry_mode.py` (update the 165 assertions)
- [x] **T005** [ENG] [BE] [US1] `BaseAgent.tool_deps() -> dict[str, Any]` (default `{}`) and `async run_undo(tool, args, *, session_id) -> ToolCall`: minimal `AgentContext(session_id=..., prompt="", intent="rollback", gate_decision=EXECUTE, retry_mode=False)`, merge `self.tool_deps()` with `args` via `_merge_deps`, call `self.call_tool(tool, ctx, _lm_args=args, **merged)`. Test with a fake agent and fake tool. · `core/contracts/ze-agents/ze_agents/base_agent.py`, `core/contracts/ze-agents/tests/test_run_undo.py`
- [x] **T006** [ENG] [BE] [US3] Gates in retry runs: remove the `retry_mode` forcing of `AWAIT_CONFIRMATION`/`DRAFT` to `EXECUTE` in `capability_check` (`execution.py` two places) and `run_delegate` (`delegate.py`). Update tests: a retry run's reversible write that needs confirmation now yields `AWAIT_CONFIRMATION`. · `core/engine/ze-core/ze_core/orchestration/nodes/execution.py`, `core/contracts/ze-agents/ze_agents/delegate.py`, their tests
- [x] **T007** [ENG] [BE] `ze-sdk`: re-export `undo_payload` from `ze_sdk` (and `ze_sdk.__all__`); extend the SDK export test. Then post "foundation landed (T002–T007)" to the Handoffs note. · `packages/ze-sdk/ze_sdk/__init__.py`, `packages/ze-sdk/tests/test_imports.py`
- [x] **T008** [P] [ENG] [PLATFORM] Migration `zc032_message_rollback.py` (ze-core, `down_revision="zc031"`): `ALTER TABLE messages ADD COLUMN IF NOT EXISTS rollback JSONB NULL`; downgrade drops it. Test mirrors `test_zc031.py`; extend `apps/ze-api/tests/test_migrate.py` chain check. · `core/engine/ze-core/ze_core/migrations/versions/zc032_message_rollback.py`, `core/engine/ze-core/tests/migrations/test_zc032.py`, `apps/ze-api/tests/test_migrate.py`
- [x] **T009** [ENG] [BE] [US5] `ze-core` message types: `ToolCallTrace.agent`, `undo_args`, `undo_note`, `call_index`; new `RollbackEntry`, `RollbackRecord`, `RollbackTrace` per data-model.md; `MessageTrace.rollback: RollbackTrace | None`; `Message.rollback: RollbackRecord | None`. Trace parse defaults for old rows. `record_trace` (`nodes/trace.py`) copies `agent`, `undo`→`undo_args`, `spec.undo_note`, and the flattened index. Tests incl. a nested delegate call keeping the delegate's agent. · `core/engine/ze-core/ze_core/conversation/messages/types.py`, `core/engine/ze-core/ze_core/orchestration/nodes/trace.py`, their tests
- [x] **T010** [ENG] [BE] `MessageStore`: load `rollback` on every message read; `set_rollback(message_id, record)` (JSONB write, overwrite). Tests with mocked pool. · `core/engine/ze-core/ze_core/conversation/messages/store.py`, its tests

**Checkpoint**: tools can return payloads, traces store them, the rollback record has a home. JR-A and JR-B start.

---

## Phase 2: Eligibility, plan and executor (US1, US2, US4, US5)  [ENG]

- [x] **T011** [ENG] [BE] [US1] [US2] Rewrite `ze_core/conversation/retry.py` per plan D3: `rollback` input, `UndoPlanEntry`, deterministic `entry_id` (R7), reverse order, new codes `not_undoable`, `undo_failed`; delete `has_reversible_action`, `has_write_action`; `confirmed_action` only for irreversible approved; `eligibility_payload` adds `plan` without `agent`/`undo_args`. Table tests: reminder-only available; reinforced loop (no payload) → `not_undoable`; reminder + email → `has_irreversible_action`; approved reversible with payload → available; workspace run; unknown tool; rollback record with `failed` → `undo_failed`; with `undone` entries → those drop out, empty plan → available text-only; failed write without payload → `not_undoable`; denied/expired gate → no action; entry ids stable across calls. · `core/engine/ze-core/ze_core/conversation/retry.py`, `core/engine/ze-core/ze_core/conversation/__init__.py`, `core/engine/ze-core/tests/conversation/test_retry_eligibility.py` (extend the 165 file)
- [x] **T012** [ENG] [BE] [US1] [US4] New `ze_core/conversation/rollback.py` `run_rollback(plan, *, message_id, thread_id, session_id, message_store) -> RollbackRecord` per plan D4: owning agent via `get_agent`, `run_undo` inside `rollback_scope`, success iff `ToolCall.success and not is_error_result(result)`, stop at first failure, rest `not_attempted`, sanitized `failure_code` (error class or the tool's error string truncated to 120 chars, no message content), `message_store.set_rollback` after each entry. Tests: order; second of three fails → third not attempted, record matches; error-dict result counts as failure; missing agent; missing undo tool; exception in undo; scope is set during the undo and cleared after. · `core/engine/ze-core/ze_core/conversation/rollback.py`, `core/engine/ze-core/tests/conversation/test_rollback.py`
- [x] **T013** [P] [ENG] [BE] [US5] `ActionRecorder.record_action` reads `current_rollback_scope()`: sets `context.message_id` and `supersedes` = latest `succeeded` record for the same `authoritative_ref` with a different `action_type`, reusing the `store.list` result it already fetches (widen the existing `limit=20` read; no second query). No scope → unchanged behavior. Tests: cancel under scope supersedes the create; lookup failure → `supersedes=None`, record still written. · `core/cognition/ze-memory/ze_memory/action_records/recorder.py`, `core/cognition/ze-memory/tests/action_records/test_recorder_rollback_scope.py`

---

## Phase 3: Per-domain undo payloads (US1, US2, US6)  [JR-A, JR-B]  — start after T007

Every task: return `"undo": undo_payload(...)` in the result exactly in the case named, never otherwise; move the agent's inline `deps={...}` into `def tool_deps(self) -> dict` and pass `deps=self.tool_deps()` to `agentic_loop` (no other change to the agent). Tests: payload present in the clean case, absent in every other case listed, and `tool_deps()` returns the same keys the loop used.

### JR-A: reminders, goals, workflows, loops, eval

- [x] **T014** [P] [JR] [BE] [US1] `set_reminder`: payload `{"reminder_id": str(rid)}` on success only (absent on parse error and past time). Reminders agent `tool_deps`. Add one test recording what `cancel_reminder` returns for an already-fired reminder (no behavior change; the executor treats an error result as a failed undo). · `plugins/ze-calendar/ze_calendar/agents/reminders/{tools.py,agent.py}`, `plugins/ze-calendar/tests/agents/reminders/test_undo_payload.py`
- [x] **T015** [P] [JR] [BE] [US1] `create_goal`: payload `{"goal_id": str(goal.id)}` on the success return only (absent on the planner-error return). Goals agent `tool_deps`. · `core/automation/ze-automation/ze_automation/agents/goals/{tools.py,agent.py}`, `core/automation/ze-automation/tests/goal_agent/test_undo_payload.py`
- [x] **T016** [P] [JR] [BE] [US1] [US2] `create_workflow`: payload `{"workflow_name": name}` on success. `enable_workflow`: payload `{"workflow_name": ...}` only when `wf.enabled` was `False` before the call. `disable_workflow`: only when it was `True`. Workflow agent `tool_deps`. Tests include the no-op cases. · `core/automation/ze-automation/ze_automation/agents/workflow/{tools.py,agent.py}`, `core/automation/ze-automation/tests/workflow_agent/test_undo_payload.py`
- [x] **T017** [P] [JR] [BE] [US2] `track_loop`: payload `{"loop_id": str(loop.id)}` only when `result.outcome == "created"` (absent for `confirmed`, `reinforced`, `revived`, and errors). Loops agent `tool_deps` (keys `loop_store`, `loop_tracker`). · `core/cognition/ze-worldstate/ze_worldstate/agents/{tools.py,agent.py}`, `core/cognition/ze-worldstate/tests/test_track_loop_undo_payload.py`
- [x] **T018** [P] [JR] [PLATFORM] Eval. Edit `eval/scenarios/retry_refused_after_write.yaml`: `retry_refused_after_reminder` becomes `retry_rollback_offered_after_reminder` (criteria: trace records `set_reminder` with an undo payload, so Retry is available with a one-entry plan); keep `retry_refused_after_goal` but change its last criterion to "Retry is unavailable while the goal waits for Start (turn pending)". New `eval/scenarios/retry_rollback.yaml`: (a) "Remind me tomorrow at 5pm to call Ana. Also email Ana that I'll call." → Retry unavailable, `has_irreversible_action`; (b) a second "keep the tax return on my radar" in the same thread → `not_undoable`. Follow the schema in `docs/eval.md`; tags `[retry, rollback]`. · `eval/scenarios/retry_refused_after_write.yaml`, `eval/scenarios/retry_rollback.yaml`

### JR-B: memory facts and priority

- [x] **T019** [JR] [BE] [US1] `ze-memory` fact write reports what it displaced. In `retriever.py`: the same-predicate `UPDATE … SET contradicted = true` gets `RETURNING id`; `_apply_semantic_contradiction_check` returns the ids it marked; `_write_fact_with_contradiction_check` sets `fact.displaced_ids` (new field on `Fact` in `ze_memory/types.py`, `list[UUID]`, default empty, never persisted) and still returns the new id. New public `retract_fact_and_restore(fact_id, restore_ids) -> None` in one transaction: raise `FactRestoreConflictError` (new, subclass of the package's `StoreError`/`ZeError`) and change nothing if the fact is missing or already contradicted, or any restore id is not currently contradicted; else set the fact `contradicted = true` and the restore ids `contradicted = false`. Check all 4 callers of `_write_fact_with_contradiction_check` still work. Tests with mocked pool. · `core/cognition/ze-memory/ze_memory/{retriever.py,types.py,errors.py}`, `core/cognition/ze-memory/tests/test_fact_restore.py`
- [x] **T020** [JR] [BE] [US1] Companion. `remember_fact`: payload `{"fact_id": str(fact.id), "restore_fact_ids": [str(i) for i in fact.displaced_ids]}` on `ok: True` only. `forget_fact(query: str = "", memory_store, fact_id: str = "", restore_fact_ids: list[str] | None = None)`: exactly one of `query` / `fact_id`, else `{"ok": False, "error": ...}`; with `fact_id` call `memory_store.retract_fact_and_restore` and return `{"ok": True, "ids": [fact_id], "restored": [...]}`, or `{"ok": False, "error": ...}` on `FactRestoreConflictError` or bad UUID. Keep the LLM-facing description about `query`; mention `fact_id` is for rollback. Companion agent `tool_deps`. Depends on T019. · `plugins/ze-personal/ze_personal/agents/companion/{tools.py,agent.py}`, `plugins/ze-personal/tests/agents/companion/test_fact_undo.py`
- [x] **T021** [JR] [BE] [US6] Priority store and service per plan D8. `PostgresPriorityOverrideStore.create()` returns `tuple[PriorityOverride, UUID | None]` (the superseded id via `RETURNING id`); update the Protocol. New `restore(override_id, prior_override_id)` (one transaction; `StalePriorityRestoreError` in `errors.py` when `override_id` is not active; reinstate the prior only when its `superseded_at` equals the new row's `submitted_at`; copy keeps anchor, relation, pinned, `submitted_at`, `contribution_domain_id`, new id). `submit_reprioritization` returns `(override, superseded_id)`; update `rest.py` to unpack. Tests: restore with prior; without prior; prior superseded by something else → only the new row is superseded; later change → error and no write. · `core/arbitration/ze-priority/ze_priority/{store.py,service.py,rest.py,errors.py}`, `core/arbitration/ze-priority/tests/{test_store_restore.py,test_service.py,test_rest.py}`
- [x] **T022** [JR] [BE] [US6] Priority tools. `reprioritize_item` → `reversibility=REVERSIBLE`, `undo_tool="restore_priority_override"`, `undo_note="Restores the priority order from before this change"`; payload `{"override_id": str(override.id), "prior_override_id": str(prior) or None}` only when an override was written. New `@tool restore_priority_override(override_store, override_id: str, prior_override_id: str | None = None)`, WRITE, IRREVERSIBLE, `effect_phrase="restored an earlier priority order"`, description says it is the undo for `reprioritize_item`; returns `{"ok": True, ...}` or `{"error": ...}` on `StalePriorityRestoreError` / bad UUID. Add it to the priority agent's tool list; priority agent `tool_deps`. Depends on T021. · `core/arbitration/ze-priority/ze_priority/{tools.py,agent.py}`, `core/arbitration/ze-priority/tests/test_tools.py`

- [x] **T023** [ENG] [BE] Repo-level declaration test (in `apps/ze-api/tests`, loads all plugins): for every REVERSIBLE tool, the keys in the plan's D1 payload table (hard-coded in the test) are accepted parameters of its `undo_tool`; `validate_tool_declarations()` passes with `restore_priority_override` registered. Plus a round trip per tool (SC-001) with fake stores: call the tool, take `ToolCall.undo`, run the undo through `BaseAgent.run_undo` on the owning agent, assert the store state equals the state before the call (reminder cancelled, goal abandoned, workflow deleted / enabled flag restored, loop dropped; facts and priority are covered by T019–T022). Depends on T014–T017, T020, T022. · `apps/ze-api/tests/test_undo_payload_contract.py` (beside the existing `test_tool_reversibility.py`)

---

## Phase 4: Retry flow (US1, US3, US4)  [ENG, with JR-C schemas first]

- [x] **T024** [JR] [BE] [PLATFORM] Schemas per contracts/api.md (start right after T010; ENG's T026–T028 wait for it): `WsRetryFrame.confirmed_plan: list[str] | None = None`; `UndoPlanEntryResponse`; `RetryEligibilityResponse.plan: list[UndoPlanEntryResponse] = []`; `RollbackEntryResponse`, `RollbackRecordResponse`; `FeedbackView.rollback`; `MessageSchema.rollback`; `WsMessageRollbackFrame` in the outbound union; error frame `code` adds `retry_partial`, plus `rolled_back: bool | None`, `rollback: RollbackRecordResponse | None`, `plan: list[UndoPlanEntryResponse] | None` (sent with `plan_changed`). `api/messages.py` maps `Message.rollback`. Schema tests. · `apps/ze-api/ze_api/api/schemas.py`, `apps/ze-api/ze_api/api/messages.py`, `apps/ze-api/tests/api/test_schemas_rollback.py`
- [x] **T025** [ENG] [BE] [US3] `invoke_retry_turn(container, thread_id, user_text, *, replaces: UUID, config_extra=None)`: config gets `retry_mode=True` and `retry_replaces=str(replaces)`; an interrupted result is returned (no restore, no error); failed/empty still restores and raises `RetryFailedError`. Update `ze_api/container.py` wrapper. Tests. · `core/engine/ze-core/ze_core/conversation/turn.py`, `apps/ze-api/ze_api/container.py`, `core/engine/ze-core/tests/conversation/test_invoke_retry_turn.py`
- [x] **T026** [ENG] [BE] [US1] `feedback_views.py`: pass the message's `rollback` into eligibility; `build_view` fills `retry.plan` and `rollback`. Tests. Depends on T011, T024. · `apps/ze-api/ze_api/feedback_views.py`, `apps/ze-api/tests/test_feedback_views.py`
- [x] **T027** [ENG] [BE] [US1] [US3] [US4] `handle_retry` per plan D5: plan guard (`undo_not_confirmed`, `plan_changed`, nothing changed); `retry_requested` unchanged; `run_rollback`; partial → `message_rollback` + `retry_partial`, stop; regenerate; completed → save with `replaces`, put `RollbackTrace` on the new trace before save, mark superseded, state `superseded`; interrupted → `send_confirmation_request`, state `rolled_back_awaiting_confirmation`; failed → state `rolled_back_retry_failed`, `retry_failed` with `rolled_back`. Text-only retries write no rollback record. Send `message_rollback` on each state change. A `retry_unavailable` refusal with `plan_changed` carries the recomputed public `plan`. `_run_retry_task`'s catch-all (`endpoint.py`) must not claim "the original reply is unchanged" when a rollback record exists: read it and say what was undone. Tests for every branch, plus a hand-built frame with a stale plan and an exception after a completed rollback. · `apps/ze-api/ze_api/api/websocket/turns.py`, `apps/ze-api/ze_api/api/websocket/endpoint.py` (`_run_retry_task` only), `apps/ze-api/tests/api/test_ws_retry.py` (extend) and new `apps/ze-api/tests/api/test_ws_retry_rollback.py`
- [x] **T028** [ENG] [BE] [US3] `confirmation.py`: when the resolved pending config has `retry_replaces`, save the produced reply (approve or deny) with `replaces` + `after_save=mark_superseded`, set state `superseded`, send `message_superseded`; when resolution produces no reply (deny-abort path, expiry), set `rolled_back_retry_failed` and send `message_rollback`. Confirm the pending config persisted by `send_confirmation_request` keeps both keys (add a test). · `apps/ze-api/ze_api/api/websocket/confirmation.py`, `apps/ze-api/tests/api/test_ws_confirmation_retry.py`
- [x] **T029** [ENG] [BE] End-to-end test in `ze-api` with fake agents and in-memory stores: (1) US1 reminder rollback then regeneration that sets a new reminder, and the new reply's eligibility is available with a one-entry plan (FR-021); assert no LLM call is made by the rollback executor itself (SC-007); (2) US4 mid-plan failure; (3) regeneration failure after full undo, then a text-only retry succeeds; (4) `plan_changed`; (5) regenerated turn calls an irreversible tool → refused; (6) pause at confirmation → deny → supersedes. · `apps/ze-api/tests/test_retry_rollback_e2e.py`

---

## Phase 5: Web (US1, US4, US5)  [JR-C]

- [x] **T030** [JR] [WEB] `make codegen` after T024 lands; commit the regenerated client. · `packages/ze-client/src/generated/**`
- [x] **T031** [JR] [WEB] [US1] `RetryButton` two-step when `retry.plan.length > 0` (plan D10): inline confirm region `role="group"` with `aria-labelledby`, list of `effect_phrase` + `undo_note`, Continue / Cancel, focus to Continue on open, Esc and Cancel close without sending, focus returns to Retry. Empty plan: one press (unchanged). Tests incl. keyboard-only and screen-reader names. · `apps/ze-web/src/features/retry-reply/ui/RetryButton.tsx`, `RetryButton.test.tsx`
- [x] **T032** [JR] [WEB] [US1] [US4] `useRetryReply`: `retry(messageId, confirmedPlan?)` sends `confirmed_plan`; handle `message_rollback`, `error` `retry_partial`, `retry_failed` with `rolled_back` (notice text from the server payload); invalidate feedback, messages, trace queries. Tests. · `apps/ze-web/src/features/retry-reply/model/useRetryReply.ts`, `useRetryReply.test.tsx`, `features/retry-reply/index.ts`, `features/reply-feedback/ui/ReplyActions.tsx` (pass the plan through), `ReplyActions.test.tsx`
- [x] **T033** [JR] [WEB] [US4] Rollback notice on the retried reply (`role="status"`): `partial` ("Ze undid …, but could not undo …"), `rolled_back_retry_failed` ("Ze undid … but could not write a new reply."), `rolled_back_awaiting_confirmation` ("Ze undid … and is waiting for your confirmation."). Survives reload (reads `rollback` from the message/feedback payload). Tests. · `apps/ze-web/src/features/reply-feedback/ui/RollbackNotice.tsx` (new), its test, `apps/ze-web/src/widgets/chat-workspace/ui/ChatWorkspace.tsx` (mount only)
- [x] **T034** [JR] [WEB] [US5] Trace panel `RollbackSection`: on a reply with `trace.rollback`: "Rolled back before this reply", entries with outcome, link to the replaced reply; on a retried reply with `rollback`: its stored record. Tests. · `apps/ze-web/src/widgets/trace-panel/ui/RollbackSection.tsx` (new), its test, `apps/ze-web/src/widgets/trace-panel/ui/TraceContent.tsx` (mount only)
- [x] **T035** [JR] [WEB] `make test-web typecheck-web` green; fix only files this lane owns. · none

---

## Phase 6: Docs  [JR-D]

Start each after its code task lands.

- [x] **T036** [P] [JR] [DOCS] `docs/architecture.md` "Reply feedback and Retry": rollback flow (plan, consent, executor, record, one retry policy, pause at confirmation); the trace-fields paragraph (`agent`, `undo_args`, `undo_note`, `call_index`); `messages.rollback` in the tables list. After T027. · `docs/architecture.md`
- [x] **T037** [P] [JR] [DOCS] `docs/native-interface.md` retry section: `confirmed_plan`, `message_rollback`, `retry_partial`, `rolled_back`, confirmation after `retry`. After T027. · `docs/native-interface.md`
- [x] **T038** [P] [JR] [DOCS] `docs/adding-an-agent.md`: replace "Ze does not undo actions on Retry in this version" with the undo payload contract (`undo_payload`, when to return it, never for no-ops or pre-existing records) and `tool_deps()`. After T014. · `docs/adding-an-agent.md`
- [x] **T039** [P] [JR] [DOCS] `docs/data-portability.md`: messages carry `rollback`. Package READMEs where they describe the touched surfaces: `core/contracts/ze-agents/README.md` (rollback scope, `run_undo`), `core/engine/ze-core/README.md` (`conversation/rollback.py`), `core/arbitration/ze-priority/README.md` (restore tool), `core/cognition/ze-memory/README.md` (fact restore), `packages/ze-sdk/README.md` (`undo_payload`). · those files
- [x] **T040** [JR] [DOCS] `AGENTS.md`: phase table row 180; layout lines for `ze_core/conversation/` (rollback.py) and `ze_agents/` (rollback.py); `zc032` in the ze-core migration row; update the Learned Workspace Fact on WRITE tools (payload per call). `specs/README.md` row 180. `specs/phases/165-response-feedback-retry/spec.md` "Deferred: Undo-then-Regenerate": one line linking to phase 180. · `AGENTS.md`, `specs/README.md`, `specs/phases/165-response-feedback-retry/spec.md`
- [x] **T041** [ENG] [DOCS] Gates and coverage. `make lint test-py test-web typecheck-web`; `graphify update .` then `graphify affected` on the T001 symbols, confirm no caller left; `packages/ze-sdk/tests/test_plugin_boundaries.py` green. Run `git diff main...HEAD --name-only` and confirm every public doc above was edited; list any doc that mentions `retry_mode`, `has_reversible_action`, `Retry`, `undo_tool` (`rtk proxy grep -rniE "retry_mode|has_reversible_action|undo_tool|\bRetry\b" docs README.md core/*/*/README.md packages/*/README.md`) and was not touched, with a reason. Set spec Status to Implemented; tick tasks through the companion `write-context.py --append` then `--materialize` (never hand-edit checkboxes); run the after-implement hook. · none

---

## Dependencies

- T001 → T002–T010. T007 unblocks JR-A (T014–T018) and JR-B (T019–T022). T010 unblocks JR-C's T024.
- T011 needs T009, T010. T012 needs T003, T005, T010, T011. T013 needs T003.
- T023 needs T014–T017, T020, T022. T025 needs T006. T026 needs T011, T024. T027 needs T012, T025, T026. T028 needs T025, T027. T029 needs all of Phases 1–4.
- T030 needs T024. T031–T034 need T030. T035 last in JR-C.
- Docs after their code tasks (see each). T041 last overall.

## Story coverage

| Story | Tasks |
|---|---|
| US1 Retry a reply that set something up | T004, T005, T011, T012, T014–T016, T019, T020, T026, T027, T029, T031, T032 |
| US2 Only clean undos are offered | T011, T016, T017, T018, T023 |
| US3 Regenerated reply can redo, never escalate | T004, T006, T025, T027, T028, T029 |
| US4 Failure is honest | T012, T027, T029, T032, T033 |
| US5 Rollback is on the record | T009, T013, T027, T034 |
| US6 Reprioritization can be undone | T021, T022 |

## Lanes

Parallel lanes never share files. Shared files belong to the ENG lane. Juniors report to the ENG lead in the Handoffs note; the Floor Reviewer reviews per phase; the ENG lead integrates and runs the gates (T041).

### Lane ENG (Claude Sonnet, lane lead)

Tasks: T001–T013, T023, T025–T029, T041.

Owns:
- `core/contracts/ze-agents/ze_agents/{tool.py,types.py,rollback.py,base_agent.py,delegate.py,__init__.py}` and their tests
- `packages/ze-sdk/ze_sdk/__init__.py`, `packages/ze-sdk/tests/test_imports.py`
- `core/engine/ze-core/ze_core/conversation/**`, `core/engine/ze-core/ze_core/orchestration/nodes/{trace,execution}.py`, `core/engine/ze-core/ze_core/migrations/versions/zc032_message_rollback.py`, and their tests
- `core/cognition/ze-memory/ze_memory/action_records/recorder.py` and its test
- `apps/ze-api/ze_api/{feedback_views.py,container.py}`, `apps/ze-api/ze_api/api/websocket/{turns,confirmation,endpoint}.py`, `apps/ze-api/tests/test_migrate.py`, new ze-api tests named in ENG tasks

Order: T001, then T002–T007 and post "foundation landed". T008–T010 next (post "T010 landed" for JR-C). Phase 2, then T025 → T026 (after JR-C's T024) → T027 → T028 → T023 (after JR-A/JR-B) → T029. T041 last.

### Lane JR-A (OpenCode flash): reminders, goals, workflows, loops, eval

Tasks: T014, T015, T016, T017, T018.

Owns: `plugins/ze-calendar/ze_calendar/agents/reminders/{tools,agent}.py`; `core/automation/ze-automation/ze_automation/agents/{goals,workflow}/{tools,agent}.py`; `core/cognition/ze-worldstate/ze_worldstate/agents/{tools,agent}.py`; `eval/scenarios/{retry_refused_after_write,retry_rollback}.yaml`; the new test files named in those tasks.

Order: wait for "foundation landed". T014–T017 in any order, T018 last.

### Lane JR-B (OpenCode flash): memory facts and priority

Tasks: T019, T020, T021, T022.

Owns: `core/cognition/ze-memory/ze_memory/{retriever.py,types.py,errors.py}`; `plugins/ze-personal/ze_personal/agents/companion/{tools,agent}.py`; `core/arbitration/ze-priority/ze_priority/{store,service,rest,errors,tools,agent}.py`; the test files named in those tasks.

Order: wait for "foundation landed". T019 → T020; T021 → T022 (the two pairs are independent).

### Lane JR-C (OpenCode flash): schemas, client, web

Tasks: T024, T030, T031, T032, T033, T034, T035.

Owns: `apps/ze-api/ze_api/api/{schemas.py,messages.py}` and `apps/ze-api/tests/api/test_schemas_rollback.py`; `packages/ze-client/src/generated/**`; `apps/ze-web/src/features/retry-reply/**`, `apps/ze-web/src/features/reply-feedback/**`, `apps/ze-web/src/widgets/trace-panel/ui/{RollbackSection.tsx,RollbackSection.test.tsx,TraceContent.tsx}`, `apps/ze-web/src/widgets/chat-workspace/ui/ChatWorkspace.tsx` (mount only).

Order: T024 as soon as ENG posts "T010 landed" (ENG's T026–T028 wait for it; post "T024 landed"). Then T030 → T031–T034 → T035.

### Lane JR-D (Docs Steward or any JR after its lane)

Tasks: T036–T040. Owns `docs/**`, `AGENTS.md`, `specs/README.md`, package READMEs listed in T039, and the one-line edit to `specs/phases/165-response-feedback-retry/spec.md`. No code files. ENG's T041 coverage check follows.

### Cross-lane files

If a JR lane needs a change in a file another lane owns, it asks the ENG lead and does not edit it. Known touch points: JR-B's T020 calls `retract_fact_and_restore` from its own T019; JR-A/JR-B import `undo_payload` from `ze_sdk` (ENG T007) and use `ToolReversibility` already in place; ENG's T027 imports the T024 schemas.
