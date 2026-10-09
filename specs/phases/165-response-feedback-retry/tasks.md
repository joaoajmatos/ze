# Tasks: Assistant Response Feedback and Retry

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required. Write fail-first. No real DB (mock asyncpg pools), no OpenRouter calls. Web tests with vitest.

**Tags**: `[BE]` Python backend · `[WEB]` ze-web / `@ze/client` consumers · `[PLATFORM]` migrations, codegen, schemas, eval, data portability · `[DOCS]` public docs, specs, AGENTS.md. `[P]` = parallelizable.

**DOCS rule (user, 2026-10-09)**: [DOCS] tasks cover every public doc the phase changes: root `README.md`, `docs/*.md`, and package READMEs, not only `AGENTS.md` and the specs index. Follow `.claude/skills/doc-style/SKILL.md` for public docs (not for `specs/` or `AGENTS.md`).

**Ownership split**: Keel = [BE] + [PLATFORM]; Prism = [WEB]; Quill = [DOCS].

---

## Phase 1: Setup

- [ ] **T001** [P] [PLATFORM] Add eval scenarios `eval/scenarios/retry_text_only.yaml` (read-only turn: retry offered and replaces reply) and `eval/scenarios/retry_refused_after_write.yaml` (reminder turn: retry refused with a reason). Follow existing scenario schema in `docs/eval.md`.
- [ ] **T002** [P] [DOCS] Mark spec 165 `Status: In progress` when implementation starts and flip the checklist file `checklists/requirements.md` to all-checked (open questions are resolved).

---

## Phase 2: Foundational (blocks all stories)

**Purpose**: shared vocabulary, reversibility declarations, trace metadata, storage. With nothing wired, no behavior changes.

### Shared types

- [x] **T003** [P] [BE] `ze-agents`: add `ClaimKind.FEEDBACK_RECORD` in `ze_agents/claims.py`; new `ze_agents/reversibility.py` with `ToolReversibility`; extend `ToolSpec` and `@tool` in `tool.py` with `reversibility`, `undo_tool`, `undo_note`, `effect_phrase`. WRITE without `reversibility` raises `AgentConfigError`; READ with any of them raises; `REVERSIBLE` requires `undo_tool`. Tests in `ze-agents/tests`.
- [x] **T004** [BE] `ze-agents`: add `validate_tool_declarations()` (every `undo_tool` resolves to a registered WRITE tool; no self-undo). Call it from `ze_core` container bootstrap after plugin tool modules load. Depends on T003.
- [x] **T005** [P] [BE] `ze-plugin`: license `FEEDBACK_RECORD` to `SourceFunction.PERCEPTION` only in `contribution.py` `_LICENSE`; add `Contribution.feedback_record` payload field. Tests: Perception accepted; Action, Executive, Reflection, Governance, Memory rejected; Perception still accepts `FACT`.
- [x] **T006** [P] [BE] `ze-sdk`: re-export `ToolReversibility`, `FeedbackKind`, `FeedbackRecord`, `submit_feedback_record`, `FeedbackStore` from the right `ze_sdk.*` modules. Update `ze-sdk` tests.

### Reversibility declarations on every WRITE tool (hard cut; classification per spec "Deferred" inventory, borderline = IRREVERSIBLE)

- [x] **T007** [P] [BE] `ze-automation` goals and workflow tools: declare reversibility, `undo_tool`, `effect_phrase` (`create_goal`→`abandon_goal`; `create_workflow`→`delete_workflow`; `enable_workflow`↔`disable_workflow`; `update_workflow`, `edit_workflow_steps` reversible via revision log; the rest irreversible). Files: `ze_automation/agents/goals/tools.py`, `ze_automation/agents/workflow/tools.py`.
- [x] **T008** [P] [BE] `ze-calendar`: `set_reminder`→`cancel_reminder`, `cancel_reminder` irreversible; `create_event`, `update_event`, `delete_event` irreversible. Files: `ze_calendar/agents/reminders/tools.py`, `ze_calendar/agents/calendar/tools.py`.
- [x] **T009** [P] [BE] `ze-messenger`: `send_email`, `archive_email`, `draft_email` all irreversible in v1. File: `ze_messenger/agents/messenger/tools.py`.
- [x] **T010** [P] [BE] `ze-workspace` and `ze-ingestion`: all workspace WRITE tools and `ingest_workspace_file` / ingestion agent writes irreversible. Files: `ze_workspace/tools.py`, `ze_ingestion/agent.py`.
- [x] **T011** [P] [BE] `ze-personal` (companion `remember_fact`→`forget_fact`; contacts `set_contact_channel`, social `confirm_project_membership`, remaining personal agent tools), `ze-priority` (`reprioritize_item` reversible), `ze-finance`, `ze-prospecting`, `ze-news` WRITE tools. Classify and declare; list each tool in the PR description.
- [x] **T012** [BE] Add a repo-level test (in `ze-api/tests`, loads all plugins) asserting every registered WRITE tool declares reversibility and `validate_tool_declarations()` passes. Depends on T007–T011.

### Trace metadata and storage

- [x] **T013** [BE] `ze-core`: extend `ToolCallTrace` with `access`, `reversibility`, `undo_tool`, `gate`, `effect_phrase`; add `MessageTrace.effects_known`; update `_parse_trace` to default missing fields (old trace → `effects_known=False`). Update `record_trace` to resolve each call from the registry, flatten nested delegate calls (research R3), record per-delegate gate outcome (152), and set `effects_known=True`. Tests incl. companion turn with nested messenger send.
- [x] **T014** [BE] Spike (≤1 hour) on research R1: prove forking from the pre-turn checkpoint (or `aupdate_state` trimming the last exchange) works with `AsyncPostgresSaver` semantics using the in-memory saver in tests plus a recorded-state test. Write the decision back into `research.md` R1. Blocks T031.
- [x] **T015** [P] [PLATFORM] Migration `zm024_feedback_records.py` in `ze-memory` per data-model.md (table, CHECKs, indexes). Down-revision `zm023`.
- [x] **T016** [P] [PLATFORM] Migration `zc031_message_supersession.py` in `ze-core` (`messages.replaces`, `messages.replaced_by`, indexes), `down_revision = "zc030"`. Verify `ze_api/migrate.py` discovers it (ze-core chain already registered); extend migration-chain test.
- [x] **T017** [BE] `ze-memory` `feedback_records/` package: `types.py` (`FeedbackKind`, `FeedbackRecord`, `FeedbackRecordDraft`, `validate_draft`), `errors.py`, `store.py` (`FeedbackStore` Protocol + `PostgresFeedbackStore`: `append` idempotent, `latest_rating`, `list_for_messages`, `history`), `contribution.py` (`submit_feedback_record` through `validate_and_submit`, rejecting wrong source function or kind). Tests mirror `action_records` tests. Depends on T003, T005, T015.
- [x] **T018** [BE] `ze-core` `MessageStore`: persist and load `replaces`/`replaced_by` on `Message`; `list_by_thread` and `list_since` exclude superseded by default (`include_superseded` flag); `mark_superseded(old_id, new_id)`; `get_message(id)`; `latest_assistant_id(thread_id)`. Update `Message` dataclass. Depends on T016.
- [x] **T019** [BE] Wire `FeedbackStore` into `ze-memory` bootstrap and the `ze-api` container so routes can inject it. It MUST NOT be added to the turn-graph dependency map. Depends on T017.

**Checkpoint**: shared vocabulary, declarations, trace metadata, tables and stores exist. No user-visible change.

---

## Phase 3: User Story 1 — Rate a reply (P1)

- [x] **T020** [BE] `ze-api/routes/feedback.py`: `PUT /api/v0/messages/{message_id}/feedback` (`setMessageFeedback`) per contracts; validates assistant message; maps `up/down/none` to feedback kinds (`none` on unrated = 200 no-op); idempotency key; `response_model`, `summary`, `description`; register router. Tests: set, change, clear, repeat key, 404 user message, 404 unknown.
- [x] **T021** [BE] `GET /api/v0/messages/feedback?ids=` (`getMessageFeedback`): `FeedbackView` per message with `current`, `history`, `trace_present`, `replaces`, `replaced_by`; omit user messages; include every stored assistant message (no trace → `trace_present=false`). Retry block filled in T033. Tests.
- [x] **T022** [P] [BE] Pydantic schemas in `ze_api/api/schemas.py` for `FeedbackView`, request, retry block; `MessageSchema` gains `replaces`, `replaced_by`; `GET /messages` gets the `include_superseded` query param (default false) wired to T018.
- [x] **T023** [PLATFORM] Regenerate `@ze/client` (`make codegen`) and commit generated artifacts; add `message_superseded` and `error.code` to WS schema (`ws_schema.py`) and regenerate WS types.
- [x] **T024** [P] [WEB] `entities/message-feedback`: `useMessageFeedbackQuery` (batch ids) and `useSetMessageFeedbackMutation` (optimistic, revert on error, client UUID idempotency key). Export from entity index. Tests.
- [x] **T025** [WEB] `features/reply-feedback/ui/ReplyActions.tsx`: thumbs up/down toggle buttons with `aria-pressed`, accessible names, hover/focus-within reveal, visible without hover on touch, 44 px targets; short non-blocking error on failure. Tests: click, toggle off, switch, error revert, keyboard.
- [x] **T026** [WEB] Add an `actions` slot to `MessageBubble` (entities/message/ui) and mount `ReplyActions` from `widgets/chat-workspace` for stored assistant messages only (user messages and non-stored frames get no controls). Fetch feedback for visible assistant ids in one batch. FSD: entity must not import the feature.

**Checkpoint**: a person can rate, change, clear; rating survives reload.

---

## Phase 4: User Story 2 — Reconstructable evidence (P1)

- [ ] **T027** [BE] Route writes call `submit_feedback_record` with Perception / `FEEDBACK_RECORD` / `prompt_supplied` / confidence 1.0 / face `WORLD` and `trace_present` from `get_trace`. Test: record + trace joined by message id exposes envelope, judgments (163/164), memory chunks, tool calls, skills, conductor ledger, compaction (SC-002).
- [ ] **T028** [BE] Guard tests: (a) no `memory_facts` write, no embedding, no memory-feed row from any feedback call; (b) static test asserting no module under `ze_core`, routing, extractor, prompts or `PriorityView` imports `ze_memory.feedback_records`, and the turn-graph deps map has no feedback store (FR-006, FR-007, SC-006/007).
- [ ] **T029** [BE] Trace retention guard: any code path that clears or rewrites `messages.trace` must skip messages that have feedback (research R6). Test.

---

## Phase 5: User Story 3 — Retry a text-only reply (P1)

- [x] **T030** [BE] `ze_core/conversation/retry.py`: `retry_eligibility(...)` pure function and `RetryEligibility`; reason codes and plain-words text from `effect_phrase` (research R7). Table-driven tests for every reason code and the action matrix in SC-003 (reminder, loop, goal, workflow, remembered fact, workspace run, sent email, outreach, calendar create, approved confirmation, denied confirmation, unknown tool, missing trace, old trace).
- [ ] **T031** [BE] `retry_mode` in the engine: `config.configurable.retry_mode`; BaseAgent tool dispatch and `delegate_to_agent` refuse WRITE tools with a model-visible message; `write_memory` skips admission, episode and dream hooks but appends the exchange to session `messages`; no goal/workflow/proactive hooks fire. Tests: zero write tool executions and zero `memory_facts` rows (SC-004). Depends on T014.
- [ ] **T032** [BE] `invoke_retry_turn` in `ze_core/conversation/turn.py`: rewind per T014 decision, run graph with original user text and `retry_mode`, return `TurnResult`. Tests with fake graph.
- [ ] **T033** [BE] `ze-api` websocket `retry` frame: new `handle_retry` in `turns.py`, dispatch in `endpoint.py`; same busy flag as turns; re-evaluate eligibility server-side; append `retry_requested`; on success save new message with `replaces`, `mark_superseded`, emit `message` then `message_superseded`; on failure emit `error` `code=retry_failed` and change nothing (FR-019); ineligible → `error` `code=retry_unavailable` with reason before any graph run. Fill the `retry` block in `getMessageFeedback`. Tests for all branches, duplicate retry → `busy`.
- [ ] **T034** [P] [PLATFORM] `ze-api` `DataDomain` for `feedback_records` (export + delete) and include `messages.replaces/replaced_by` in message export; extend `data-portability` tests (FR-027).
- [ ] **T035** [WEB] `features/retry-reply`: `useRetryReply(threadId)` sends the WS frame, tracks retrying per thread, handles `message_superseded` (swap in place, invalidate feedback and trace queries), `retry_failed` (notice, original unchanged), `retry_unavailable`, `busy`. Extend `ws-client` types. Tests.
- [ ] **T036** [WEB] Retry button in `ReplyActions` (latest assistant reply only), disabled while retrying/busy/disconnected (`disconnected` reason client-side). Thread history query excludes superseded by default. Tests.

---

## Phase 6: User Story 4 — Retry explains when unsafe (P1)

- [ ] **T037** [WEB] Disabled Retry shows `reason_text` as visible/`aria-describedby` text reachable by keyboard and screen reader, on focus and tap, not only a tooltip (FR-023). Tests including axe-style name/description checks. Hide the control for turns pending confirmation.
- [ ] **T038** [BE] Server refuses hand-built retry requests for every ineligible class with the same reason as the batch endpoint (parametrized test calling the WS handler directly; FR-016, US4-7).
- [ ] **T039** [BE] Per-delegate confirmation interaction tests (152): approved write → `confirmed_action`; denied/expired → not an action; paused turn → `turn_pending`; two concurrent gates on one thread.

---

## Phase 7: User Story 5 — Feedback in the trace panel (P2)

- [ ] **T040** [WEB] `widgets/trace-panel/ui/FeedbackSection.tsx` inside `TraceEntry`: current rating, history with times, "Retried" with link to replacement, "Replaces an earlier reply" link, "No feedback yet", "no trace recorded" case. Live update on mutation without reload. Tests alongside `JudgmentsSection.test.tsx`.
- [ ] **T041** [WEB] For messages with feedback but no trace, list them in the panel with the "no trace recorded" marker (US5-5). Test.

---

## Phase 8: Polish, eval, docs

- [ ] **T042** [PLATFORM] Run the two eval scenarios (T001) against `make dev-eval`; fix drift. Record in `docs/eval.md` only if the scenario schema changed.
- [ ] **T043** [BE] Full gates: `make lint`, `make test-py`, `make test-web`, `make typecheck-web`. Fix everything.
- [ ] **T044** [PLATFORM] Execute `quickstart.md` end to end against `make dev-full`; note deviations.
- [ ] **T045** [P] [DOCS] `AGENTS.md`: add phase 165 row to the phase table, `ze-memory` `zm024` and `ze-core` `zc031` in the migration table, `feedback_records/` and `retry.py` in the layout, Perception's second licence in the seam notes, and a Learned Facts line "every WRITE tool declares reversibility". `AGENTS.md` is exempt from doc-style.
- [ ] **T046** [P] [DOCS] Specs: update `specs/README.md` row 165 (title, link to this spec, status), set spec.md `Status: Implemented` when done; update `specs/arch/contribution-seam.md` (Perception licence, new producer) and `specs/arch/ze-doctrine.md` licence table; add a short note in `specs/arch/claim-topology.md` for the new kind.
- [ ] **T047** [P] [DOCS] Root `README.md`: mention reply feedback and Retry in the features overview if it lists chat/trace capabilities; otherwise record "no change" in the PR description. Apply doc-style.
- [ ] **T048** [P] [DOCS] `docs/native-interface.md`: reply controls, Retry rules and unavailable reasons, `retry` / `message_superseded` frames, `error.code`, superseded messages hidden from history.
- [ ] **T049** [P] [DOCS] `docs/memory.md` and `docs/cognitive-architecture.md`: feedback records are evidence not facts, Perception's second licence, `feedback_records` table, no consumer in v1; `docs/data-portability.md`: feedback in export/delete.
- [ ] **T050** [P] [DOCS] `docs/architecture.md`: trace carries effect metadata, retry flow and `retry_mode`, supersession on `messages`; `docs/package-architecture.md` if package contents are listed there.
- [ ] **T051** [P] [DOCS] `docs/adding-an-agent.md`, `docs/extending-ze.md`, `docs/sdk.md`: `@tool` now requires `reversibility` for WRITE tools, with `undo_tool`, `undo_note`, `effect_phrase`, startup validation, how to classify, and the retry consequence. Update every `@tool(access=WRITE...)` code sample in these files.
- [ ] **T052** [P] [DOCS] `docs/frontend.md` (new `message-feedback`, `reply-feedback`, `retry-reply` slices and the `actions` slot), `docs/eval.md` (new scenarios), `docs/testing.md` (new targets if any), `docs/configuration.md` (state "no new config" or document any added).
- [ ] **T053** [P] [DOCS] Package READMEs: `ze-agents` (tool declaration), `ze-memory` (feedback_records), `ze-plugin` (licence table), `ze-core` (retry, supersession, trace metadata), `ze-sdk` (new exports), `apps/ze-api` (routes, WS frames), `apps/ze-web`, `packages/ze-client` if it has a README, and each package whose tools gained declarations: `ze-automation`, `ze-calendar`, `ze-messenger`, `ze-workspace`, `ze-ingestion`, `ze-personal`, `ze-finance`, `ze-prospecting`, `ze-news`. Use `docs/package-readme-template.md`.
- [ ] **T054** [P] [DOCS] Run the doc-style skill over every changed public doc (T047–T053); where a diagram helps (retry flow, feedback-to-trace link), use `diagram-design` for `docs/architecture.md` or `docs/native-interface.md`.
- [ ] **T055** [DOCS] Docs coverage check: `git diff --name-only main` must show each doc touched in T047–T053 or an explicit "no change" line in the PR description. Companion write-context `--append` then `--materialize` for these tasks.

---

## Dependencies

- Phase 2 blocks everything. T003→T004,T007–T011→T012; T005→T017; T015→T017; T016→T018; T014→T031→T032→T033.
- T023 needs T020–T022 (route shapes final) and T038-independent. US1 (T020–T026) needs T017–T019. US2 needs US1 route. US3 needs T013, T018, T030–T032. US4 builds on US3. US5 needs T021.
- [WEB] work can start after T023 (client regenerated) using the contract in `contracts/api.md`.
- [DOCS] T045–T055 can draft in parallel once contracts are stable; finalize after T043.

## Parallel lanes

- Keel: T003–T019, T020–T022, T027–T034, T038–T039, T042–T044.
- Prism: T024–T026, T035–T037, T040–T041 (blocked on T023).
- Quill: T002, T045–T055.
