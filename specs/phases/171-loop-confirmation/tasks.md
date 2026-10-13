# Tasks: Loop Confirmation Path

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Unit tests use fakes. Real-row tests live in `apps/ze-api/tests/pg/` (marker `pg`, 170 harness). The real-E5 held-out test is `@pytest.mark.slow`. Never call OpenRouter or System One in tests.

**Lanes**: `[ENG]` = Claude Sonnet lane lead (cross-package design, honesty enforcement, calibration judgment, integration, gates). `[JR]` = OpenCode flash junior (exact files and behavior given). Each user-story phase carries its lane tag; a task that differs carries its own. See **Lanes** at the end.

**Tags**: `[BE]` backend Python · `[WEB]` ze-web and generated client · `[PLATFORM]` Makefile, eval and calibration data · `[DOCS]` docs, READMEs, specs.

**Normative references**: confirm, tool, offers, recap text, caps: [contracts/confirm-and-offer.md](./contracts/confirm-and-offer.md). Detector and calibration: [contracts/open-query.md](./contracts/open-query.md). Types and state keys: [data-model.md](./data-model.md).

**Rules for the implementer**
- 171 starts only after Phases 169 and 170 are on `main` and merged into this branch (plan.md "Dependencies and merge order").
- Before changing any signature in plan.md "Blast radius", run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep -rn "<name>" --include='*.py' --include='*.ts' --include='*.tsx' apps core packages`, and update every caller and test double in the same change. graphify misses duck-typed calls through `config["configurable"]["turn_surfacer"]`; grep for them.
- No migration. Do not edit `PostgresLoopStore.transition`, `stamp_declared` (169), `list_drift_candidates`, `record_corroboration` (170), the loop gate (168), or the Priority page.
- `ze_core` must not import `ze_priority` or `ze_worldstate`.
- `get_logger(__name__)`; no `print()`; typed `ZeError` subclasses only.
- Shared worktree: stage and commit only your own files with explicit paths (`git add <paths>; git commit -m ... -- <paths>`); never `git add -A`, `git stash`, reset or checkout files you do not own. Commit only when the ENG lead or Maestro asks.
- Tick tasks with the companion `write-context.py --append` then `--materialize`; never hand-edit checkboxes.
- If a step disagrees with the code you find, stop and report the difference to the ENG lead (juniors) or the Spec Architect / Maestro (ENG); do not redesign.

**Ordering**: phases run in order within a lane. `[P]` tasks touch different files and may run together. Cross-lane order is in **Lanes**.

---

## Phase 1: Gate  [ENG]

- [x] T001 [ENG] [BE] Confirm 169 and 170 are on this branch: `rtk proxy grep -n "def stamp_declared\|def track_loop_succeeded\|strip_track_claims\|DECLARED_CONFIDENCE" core/cognition/ze-worldstate/ze_worldstate/store.py core/cognition/ze-worldstate/ze_worldstate/types.py core/contracts/ze-agents/ze_agents/nested_tools.py`, `ls apps/ze-api/tests/pg/conftest.py`, and `rtk proxy grep -n "drift_deadline <= now()" core/cognition/ze-worldstate/ze_worldstate/store.py`. Read both diffs (`git log --oneline main -- specs/phases/169-loop-track-tool specs/phases/170-executive-repair`). Write any name or behavior that differs from plan.md "Dependencies" into the Handoffs note and stop if a hard dependency is missing. · none
- [x] T002 [ENG] [BE] Run `graphify update .` then `graphify affected` for `TurnSurfacing`, `ResumeRecap`, `surface_loops`, `track_loop_succeeded`, `MessageTrace`, `LoopsAgent`; compare with plan.md "Blast radius" and add any new caller to your report. · none

---

## Phase 2: Foundational (trace path and shared types)  [ENG]

**Purpose**: the state keys and trace field that US4 and US5 write, and the `LoopOffer` type. Blocks US4 and US5.

- [x] T003 [ENG] [BE] Fail-first: (a) `core/engine/ze-core/tests/conversation/test_message_store.py`: a stored trace with `loop_offer_ids: ["<uuid>"]` round-trips; an old row without the key parses to `[]`. (b) `core/engine/ze-core/tests/orchestration/nodes/` (the file that tests `record_trace`; find it with `rtk proxy grep -rln "record_trace" core/engine/ze-core/tests`): state `loop_offer_ids=["a"]` lands on `MessageTrace.loop_offer_ids`; missing key → `[]`. (c) `apps/ze-api/tests/api/` (the file testing `GET /api/v0/messages/{id}/trace`; find with `rtk proxy grep -rln "resume_recap_applied" apps/ze-api/tests`): response includes `loop_offer_ids`. · those test files
- [x] T004 [ENG] [BE] Add `open_items_query: bool` and `loop_offer_ids: list[str]` to `AgentState` (`core/engine/ze-core/ze_core/orchestration/state.py`, beside `resume_recap_applied`, with one-line comments naming `fetch_context` as the writer). Add `loop_offer_ids: list[str] = field(default_factory=list)` to `MessageTrace` (`ze_core/conversation/messages/types.py`), parse it in `store.py` (`list(data.get("loop_offer_ids") or [])`), copy it in `ze_core/orchestration/nodes/trace.py` (`list(state.get("loop_offer_ids") or [])`). Makes T003(a)(b) pass. · listed files
- [x] T005 [ENG] [WEB] Add `loop_offer_ids: list[str] = []` to `MessageTraceResponse` in `apps/ze-api/ze_api/api/schemas.py` and pass it in `apps/ze-api/ze_api/api/messages.py` (beside `resume_recap_applied`). Run `make codegen`; commit the regenerated `packages/ze-client/src/generated/*`. Makes T003(c) pass. · listed files
- [x] T006 [ENG] [BE] Add `LoopOffer` (frozen dataclass: `loop_id: UUID`, `title: str`, `provenance: str`) to `core/arbitration/ze-priority/ze_priority/types.py` and export it from `ze_priority/__init__.py`. Add constants to `ze_priority/turn.py`: `OFFER_LIMIT = 3`, `OFFER_COOLDOWN_HOURS = 168`, `RECAP_LIMIT = 5`, `OPEN_QUERY_LIMIT = 10`, `OFFER_EVENT_PREFIX = "worldstate_loop_offer:"`. · listed files

**Checkpoint**: `make test-core test lint` green.

---

## Phase 3: User Story 1 - Review suspected loops on a page (Priority: P1)  [JR] (lane JR-web)

**Goal**: `/loops` page mounting `LoopReviewList`, grouped, in the Automation nav group.

**Independent Test**: vitest renders the page with a mocked loops query (one suspected, one active, one drifting) and checks headings, order, buttons and mutations; nav test checks the route.

- [x] T007 [P] [US1] [JR] [WEB] Fail-first tests: (a) `apps/ze-web/src/shared/config/nav-routes.test.ts`: `navRoutes` contains `{path: "loops", label: "Open loops", showInMobileNav: false}` directly after `priority`; `automationNavRoutes.map(r => r.path)` equals `["goals", "priority", "loops", "workflows", "skills"]` in `navRoutes` order (check the current order in the file and assert the real resulting order); `getRouteLabel("/loops")` is `"Open loops"`. (b) `apps/ze-web/src/widgets/loop-review/ui/LoopReviewList.test.tsx` (extend, keep existing cases): with loops `[active A, suspected S1, drifting D, suspected S2]` the heading "Needs your OK" comes before "Tracking", S1 and S2 are under the first, A and D under the second; suspected rows show "Keep" and "Drop" and no "Close"; active/drifting rows show "Close" and "Drop"; clicking Keep calls the mutation with `{loopId, kind: "confirm"}`; with only active loops the "Needs your OK" heading is absent; with only suspected loops "Tracking" is absent. (c) `apps/ze-web/src/pages/loops/ui/LoopsPage.test.tsx` (new): renders the widget (mock `@/widgets/loop-review` and assert it is rendered). · those files
- [x] T008 [US1] [JR] [WEB] `apps/ze-web/src/shared/config/nav-routes.ts`: import `ListChecks` from `lucide-react`; add `{ path: "loops", label: "Open loops", icon: ListChecks, showInMobileNav: false }` right after the `priority` entry; add `r.path === "loops"` to the `automationNavRoutes` filter. Makes T007(a) pass. · that file
- [x] T009 [US1] [JR] [WEB] `apps/ze-web/src/app/router/routes.ts`: add `loops: () => import("@/pages/loops").then((m) => ({ default: m.LoopsPage })),` to `lazyByPath`. · that file
- [x] T010 [US1] [JR] [WEB] Create `apps/ze-web/src/pages/loops/index.ts` (`export { LoopsPage } from "./ui/LoopsPage";`) and `apps/ze-web/src/pages/loops/ui/LoopsPage.tsx`: a function component returning `<LoopReviewList />` imported from `@/widgets/loop-review`, wrapped the same way `apps/ze-web/src/pages/priority/ui/PriorityPage.tsx` wraps its widget (copy its outer container classes; do not add a page title, the top bar shows it). Makes T007(c) pass. · new files
- [x] T011 [US1] [JR] [WEB] `apps/ze-web/src/widgets/loop-review/ui/LoopReviewList.tsx`: inside `ListPage`, split `loops` into `suspected` (state `suspected`) and `tracking` (states `active`, `drifting`), keeping server order within each; render a section per non-empty group with an `h2` (`text-sm font-medium text-smoke mb-2`) "Needs your OK" then "Tracking"; rename the suspected button label "Confirm" → "Keep" (same mutation); leave provenance/confidence line, Close, Drop, empty and error states unchanged. Makes T007(b) pass. · that file
- [x] T012 [US1] [JR] [WEB] Run `make test-web typecheck-web`; fix only files of this lane. Report to the ENG lead. · none

**Checkpoint**: `/loops` reachable from the Automation group and works against the existing REST confirm/drop.

---

## Phase 4: User Story 2 - Every confirm means the same thing (Priority: P1)  [ENG]

**Goal**: one confirm write (0.9, fresh 7-day deadline) for page, REST, chat.

**Independent Test**: `test_review.py` with a fake store; REST route test reports confidence 0.9.

- [x] T013 [US2] [ENG] [BE] Fail-first: (a) `core/cognition/ze-worldstate/tests/test_review.py`: `confirm_loop` calls `transition(id, "active")` (no `user_asked`), then `stamp_declared(id, confidence=DECLARED_CONFIDENCE, deadline=≈now+7d)` (assert within 5 s), never `set_drift_deadline`; the returned loop has confidence 0.9, `drift_rationale` None, deadline set, provenance unchanged (`"email"` in, `"email"` out); `InvalidLoopTransitionError` and `LoopNotFoundError` from `transition` propagate and `stamp_declared` is not called. Update the existing `test_confirm_loop_transitions_suspected_to_active` fake to implement `stamp_declared`. (b) `apps/ze-api/tests/api/test_loops_route.py`: confirm returns `confidence == 0.9`; existing 404/409 cases unchanged. · those files
- [x] T014 [US2] [ENG] [BE] Implement per contracts/confirm-and-offer.md in `core/cognition/ze-worldstate/ze_worldstate/review.py` (import `DECLARED_CONFIDENCE` from `ze_worldstate.types`, `DEFAULT_DRIFT_WINDOW_DAYS` from `ze_worldstate.drift`; drop the `set_drift_deadline` call; update the docstring: user confirmation is stamped like a declaration, provenance is kept). Run `make test-worldstate test`. · that file

**Checkpoint**: the page's Keep (US1) now produces 0.9.

---

## Phase 5: User Story 3 - Confirm or drop in chat (Priority: P1)  [ENG]

**Goal**: `confirm_loop` tool; tracking claims earned by confirm; 168 gate skipped after a confirm.

**Independent Test**: tool table tests, honesty table, scripted-agent test, gate-skip test, retry-eligibility test.

- [x] T015 [P] [US3] [ENG] [BE] Fail-first `core/cognition/ze-worldstate/tests/test_confirm_loop_tool.py` (new), one test per row of the `confirm_loop` table in contracts/confirm-and-offer.md, using a fake `LoopStore` with `transition`/`stamp_declared`; plus: the tool's `ToolSpec` declares WRITE, `REVERSIBLE`, `undo_tool == "drop_loop"`, non-empty `undo_note`, `effect_phrase == "confirmed an open loop"`; `validate_tool_declarations()` passes. · new file
- [x] T016 [P] [US3] [ENG] [BE] Fail-first honesty and skip: (a) `core/contracts/ze-agents/tests/test_track_loop_honesty.py`: rename imports to `tracking_earned`; add rows: "I'll keep track of the bank switch." kept when a `confirm_loop` call returned `{"ok": True, ...}` (top level and nested in a `delegate_to_agent` result); stripped to `COULD_NOT_TRACK` when `confirm_loop` returned `{"ok": False, ...}`; PT row "Vou acompanhar isso." same pair. (b) `core/engine/ze-core/tests/orchestration/test_loop_admission_node.py`: a result with a successful `confirm_loop` call skips `loop_admission`; a failed one runs it. (c) `core/engine/ze-core/tests/conversation/test_retry_eligibility.py`: a trace whose tool calls include `confirm_loop` is not retryable with the reversible-action reason (mirror the existing `track_loop` or reversible-tool case). · those files
- [x] T017 [US3] [ENG] [BE] `core/contracts/ze-agents/ze_agents/nested_tools.py`: rename `track_loop_succeeded` → `tracking_earned`, match `tool_name in {"track_loop", "confirm_loop"}`; update its use inside `enforce_domain_cancel_confirmations`. Update the caller in `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` (and any other `rtk proxy grep -rn track_loop_succeeded` hit). No alias. Makes T016(a)(b) pass. · listed files
- [x] T018 [US3] [ENG] [BE] `core/cognition/ze-worldstate/ze_worldstate/agents/tools.py`: add `confirm_loop` exactly as in contracts/confirm-and-offer.md (import `review.confirm_loop as review_confirm`; catch `ValueError` for the UUID, `LoopNotFoundError`, `InvalidLoopTransitionError`, then `Exception` → generic error + `log.warning("confirm_loop_failed", ...)`). Makes T015 pass. · that file
- [x] T019 [US3] [ENG] [BE] `core/cognition/ze-worldstate/ze_worldstate/agents/agent.py`: apply the "Loops agent instructions (additions)" section of the contract to `tools`, the `manage` intent text, `description`, `routing_criteria` and `_AGENT_INSTRUCTIONS`; keep `strip_track_claims=True`. Add a scripted-LLM case to `core/cognition/ze-worldstate/tests/test_loop_agent_cancel.py`: the model calls `list_open_loops`, `confirm_loop(S1)`, `drop_loop(S2)` and replies "I'll keep track of the bank switch and dropped the dentist one."; assert both transitions and that the reply is unchanged. A second case where `confirm_loop` fails and the model still claims tracking: reply is `I could not track that.` Run `make test-worldstate test-agents test-core`. Makes T016(c) pass via the declaration. · listed files

**Checkpoint**: chat confirm works when the user names a suspected loop.

---

## Phase 6: User Story 4 - Resume question about at most 3 suspected loops (Priority: P1)  [ENG]

**Goal**: offers selected, cooled down, recorded, rendered into the recap, traced.

**Independent Test**: `test_turn.py` offer cases; `test_context.py` recap and state cases.

- [x] T020 [P] [US4] [ENG] [BE] Fail-first `core/arbitration/ze-priority/tests/test_turn.py` for `resume_loop_offers` (fake loop store, fake push log with `was_sent_within_hours`/`log`): 5 suspected loops → 3 returned, ordered by confidence desc then `created_at` desc, `created_at=None` last; a loop with a cooldown hit is skipped and the next one fills the slot; each returned loop logged once as `worldstate_loop_offer:<id>`; non-suspected states are never read (assert `list(states=["suspected"])`); `push_log=None` → `[]`; `list` raises → `[]`; `was_sent_within_hours` raises → `[]` and nothing logged; `log` raises for one → offers still returned; SC-002 sequence: a fake push log that stores `(event_type, sent_at)` and answers `was_sent_within_hours` against an injected `now`, 4 suspected loops, 14 simulated daily resumes (advance `now` by 24 h, call `resume_loop_offers()` each day) → no loop offered more than 2 times and never twice within 7 days (`TurnSurfacing` takes an optional `clock: Callable[[], datetime]` only if the fake cannot do this alone; prefer putting the clock in the fake). · that file
- [x] T021 [US4] [ENG] [BE] Implement `TurnSurfacing.resume_loop_offers` in `core/arbitration/ze-priority/ze_priority/turn.py` per the contract pseudocode (warnings: `turn_surfacing_offer_list_failed`, `turn_surfacing_offer_cooldown_failed`, `turn_surfacing_offer_log_failed`). Makes T020 pass. · that file
- [x] T022 [P] [US4] [ENG] [BE] Fail-first `core/engine/ze-core/tests/orchestration/nodes/test_context.py` (extend the surfacer double with `resume_loop_offers = AsyncMock(return_value=[...])`, offers as `SimpleNamespace(loop_id=uuid, title=...)`): (a) gap + 2 offers → `agent_context.resume_recap` contains the exact block from the contract with both titles, after any "Still open" lines; the node returns `loop_offer_ids` with both ids as strings and `resume_recap_applied` True; (b) gap, offers only (no narrative, no items, no workflows) → recap still applied; (c) no gap → `resume_loop_offers` not awaited, `loop_offer_ids == []`; (d) gap with `config["configurable"]["retry_mode"] = True` → not awaited, `[]`; (e) `resume_loop_offers` raises → turn completes, `[]`. Update `test_context_continuity_composition.py` if its double lacks the method. · those files
- [x] T023 [US4] [ENG] [BE] `core/engine/ze-core/ze_core/orchestration/nodes/context.py`: add `loop_offers: list[Any]` to `ResumeRecap` (`has_content` and `render` per data-model.md and the contract's exact text); in `_assemble_resume_recap` call `surfacer.resume_loop_offers()` unless `configurable.get("retry_mode")`, in its own try/except (`resume_recap_loop_offers_failed`); return `loop_offer_ids` from `fetch_context` on every path. Makes T022 pass. · that file

**Checkpoint**: a resume turn carries the question instruction; the trace lists the offered ids.

---

## Phase 7: User Story 6 - Recap cap (Priority: P2)  [ENG]

(Done before US5 because both edit `turn.py` and `context.py`; same lane, sequential.)

- [x] T024 [US6] [ENG] [BE] Fail-first: `core/arbitration/ze-priority/tests/test_turn.py`: `recap_mentions(limit=5)` over 8 merged items returns the first 5 in merged order (a pinned item placed by the 127 merge stays first); `limit=None` returns all. `core/engine/ze-core/tests/orchestration/nodes/test_context.py`: the resume path awaits `recap_mentions(limit=5)`; the open-priorities path awaits `recap_mentions(limit=10)` (use `assert_awaited_with`). · those files
- [x] T025 [US6] [ENG] [BE] `turn.py`: `recap_mentions(self, limit: int | None = None)` slices after the merge. `context.py` cannot import `ze_priority`, so define `_RECAP_LIMIT = 5` and `_OPEN_QUERY_LIMIT = 10` there with a one-line comment naming `ze_priority.turn.RECAP_LIMIT` / `OPEN_QUERY_LIMIT` as the values they mirror, and pass them. T024's `assert_awaited_with` tests pin both sides. Makes T024 pass. · `turn.py`, `context.py`

---

## Phase 8: User Story 5 - Language-neutral "what's open" (Priority: P2)  [ENG]; T026–T027 [JR] (lane JR-data)

**Goal**: E5 detector replaces the regex; threshold from offline calibration.

**Independent Test**: fake-embedder unit tests; `--check-sets`; the single held-out verdict; slow regression test.

- [x] T026 [P] [US5] [JR] [PLATFORM] Write the datasets per contracts/open-query.md. **First** `eval/calibration/open_query_holdout.jsonl` (≥ 20 EN + ≥ 20 PT, about half positives, hard negatives as listed in research.md R5, European Portuguese spelling), then `eval/calibration/open_query.jsonl` (≥ 40 EN + ≥ 40 PT, same mix, no text shared with the held-out file, no example from `OPEN_QUERY_EXAMPLES` verbatim). Positives: questions asking what is open / pending / left / on the user's plate. The **tuned** set (not held-out) MUST include at least 4 EN and 4 PT paraphrases of "what am I still sitting with?" style questions (e.g. "what's still weighing on me", "what am I still carrying around", "o que ainda me anda a pesar", "com o que é que ainda ando"), not the verbatim example text; source: Tally's 169 e2e, where that phrasing routed to companion (E5 gap 0.029). The detector answers it for any routed agent. Negatives: opening hours, opening files/doors/windows, open job positions, "what's on TV", what to cook, and statements about one specific worry ("I'm worried about the visa") that are not a request to list. Commit the held-out file in its own commit before T027. Report the counts to the ENG lead. · two new files
- [x] T027 [US5] [JR] [PLATFORM] Write `eval/calibration/open_query.py` per the script table in contracts/open-query.md (argparse `--set tuned|holdout`, `--threshold`, `--check-sets`; loads the embedder with `ze_core.embeddings.get_embedder()`; builds `OpenQueryDetector(embedder, threshold=...)` from `ze_priority.open_query` once T029 lands; until then `--check-sets` must already work). Add to `Makefile`: a help line under the calibrate group ("calibrate-open-query  LOCAL E5 run over eval/calibration/open_query.jsonl; free; --check-sets is offline"), the target `calibrate-open-query:` running `uv run python eval/calibration/open_query.py $(ARGS)`, and the name in the `.PHONY` line. Run `make calibrate-open-query ARGS="--check-sets"`. · `eval/calibration/open_query.py`, `Makefile`
- [x] T028 [P] [US5] [ENG] [BE] Fail-first: (a) `core/arbitration/ze-priority/tests/test_open_query.py` (new) with a fake embedder mapping strings to fixed unit vectors: best similarity is the max dot product; at-threshold → True, below → False; examples embedded once across many calls (call count 1); `embedding is None` → False; embedder raising → False and later calls retry the lazy load. (b) `test_turn.py`: replace the regex tests with `is_global_open_query(embedding)` delegating to an injected detector double; delete `test_is_global_open_query_positive/negative`. (c) `core/engine/ze-core/tests/orchestration/nodes/test_context.py`: the surfacer double's `is_global_open_query` receives the embedding (not the prompt); the node returns `open_items_query` True/False accordingly; detector raising → False and the turn completes; the note is built only when True. (d) `core/engine/ze-core/tests/orchestration/nodes/test_loop_surfacing.py`: remove `is_global_open_query` from the doubles; with `state["open_items_query"] = True` the node returns `{}` without calling `inline_mentions`. · those files
- [x] T029 [US5] [ENG] [BE] Implement `core/arbitration/ze-priority/ze_priority/open_query.py` per contracts/open-query.md (start with the listed examples and `OPEN_QUERY_THRESHOLD = 0.90` as a placeholder until T031); export `OpenQueryDetector` from `ze_priority/__init__.py`. In `turn.py`: delete `_GLOBAL_OPEN_RE` and the static method; constructor gains `embedder` and `open_query_detector=None` (default `OpenQueryDetector(embedder)`); instance `is_global_open_query(embedding)`. In `context.py`: compute `open_items_query` once from `prompt_embedding` (guarded), pass it to `_open_priorities_note` (signature `(open_items_query: bool, config)`), return it. In `loop_surfacing.py`: read `state.get("open_items_query")`, drop the `prompt` lookup. Makes T028 pass. · listed files
- [x] T030 [US5] [ENG] [BE] Wire the embedder: `apps/ze-api/ze_api/container.py` passes `embedder=shared.embedder` to `TurnSurfacing`; update `_real_push_stack` (and any other constructor) in `apps/ze-api/tests/api/test_workspace_followthrough.py` with a stub embedder. Run `make test test-priority test-core lint`. · listed files
- [x] T031 [US5] [ENG] [PLATFORM] Calibrate: `make calibrate-open-query` (tuned). Refine `OPEN_QUERY_EXAMPLES` and pick `OPEN_QUERY_THRESHOLD` on the tuned set only. Then exactly one `make calibrate-open-query ARGS="--set holdout --threshold <T>"`. Record recall, FPR, threshold and PASS/FAIL per language in research.md "Verdict". On FAIL follow research.md R5 (new held-out file, one rerun), and report to the Spec Architect/Maestro if it fails twice. Set the final constants in `open_query.py`. Add `core/arbitration/ze-priority/tests/test_open_query_holdout.py` (`@pytest.mark.slow`, real `get_embedder()`): held-out recall ≥ 0.9 and FPR ≤ 0.05 per language at the shipped constants. Run `make test-priority SLOW=1`. · `open_query.py`, `research.md`, new test

**Checkpoint**: "O que tenho em aberto?" sets the open-priorities note.

---

## Phase 9: Real-Postgres check (US2 + US4)  [ENG]

- [x] T032 [ENG] [BE] `apps/ze-api/tests/pg/test_loop_confirmation_pg.py` (new, `@pytest.mark.pg`, 170 harness fixtures): (a) create a suspected loop with the real `PostgresLoopStore`, call `review.confirm_loop`; row has state `active`, confidence 0.9, `confirmed_at = updated_at`, deadline ≈ now+7d; move the deadline 1 day into the past; `DriftSweepJob` moves it to `drifting` (proves confirm feeds 170's predicate). (b) with the real `PushLogStore` and `TurnSurfacing` (fake priority view and embedder), two suspected loops: first `resume_loop_offers()` returns both and writes two `push_log` rows; a second call returns `[]`; after `UPDATE push_log SET sent_at = now() - interval '8 days'` it returns both again. Run `make test-pg`. · new file

---

## Phase 10: User Story 7 - Evals and routing rows (Priority: P3)  [JR] (lane JR-data)

- [x] T033 [P] [US7] [JR] [PLATFORM] `eval/scenarios/loops.yaml` (created by 169; append, do not edit its scenarios): add `loops-whats-open-en` ("What's still on my plate?") and `loops-whats-open-pt` ("O que tenho em aberto?"), single-turn, tags `[loops, executive, phase-171]`, no `expected_agent` (any speaker may answer), judge criteria: "The reply either lists open items (loops, goals, workflows) or says plainly that nothing is open; it does not answer a different question (opening hours, files)". Match the YAML shape of the existing scenarios in that file. Check with `ze_list_scenarios` or `python eval/run.py --list` if available. · that file
- [x] T034 [P] [US7] [JR] [PLATFORM] `eval/calibration/routing.jsonl`: append four training rows in the file's existing shape with gold agent `loops`: EN "Yes, keep the bank switch one and drop the dentist thing.", EN "Keep tracking the visa renewal you asked me about.", PT "Sim, fica com a do banco e esquece a do dentista.", PT "Podes manter a renovação do passaporte que perguntaste?". Ids `train-loops-confirm-en-1/2`, `train-loops-confirm-pt-1/2`. Also append two listing rows, gold `loops`: EN "What am I still sitting with these days?" (`train-loops-list-en-1`) and PT "Com o que é que ainda ando às voltas?" (`train-loops-list-pt-1`). Check first that neither text already exists in `routing.jsonl` or any `routing_holdout*.jsonl`; if one does, pick another paraphrase. Training rows document the intent; they do not change routing bars (no recalibration). Never edit `routing_holdout*.jsonl` (`git diff --stat eval/calibration/routing_holdout*` must be empty). Validate offline: every line parses as JSON, ids are unique across the file, and the gold field names match the existing rows (`python -c` one-liner or the script's own set check if `eval/calibration/routing.py` has one). No recalibration of routing bars (as in 169). · that file

---

## Phase 11: Polish and gates  [ENG]

- [x] T035 [ENG] Full gates: `make test-py`, `make test-pg`, `make test-web`, `make typecheck-web`, `make lint`, `make test-priority SLOW=1`. Boundary checks from plan.md (`graphify path "ze_priority.open_query" "ze_core"`; the ze_core import grep). Fix or report. · none
- [ ] T036 [ENG] Ask QA (Tally) for the end-to-end check in quickstart.md (manual steps 2–4) and a live run of the two new eval scenarios (`make dev-eval`, then the eval runner with `--tag phase-171`). Record results in the Handoffs note. · none

---

## Phase 12: Documentation  [JR] (lane JR-docs, after T035)

Follow the `doc-style` skill for README and `docs/*.md`.

- [ ] T037 [P] [JR] [DOCS] `README.md`: in "### Open loops" add two sentences: Ze asks at the start of a new session whether to keep track of up to three loops it noticed, and the Open loops page (Automation) lists them for review; in the agents table row for `loops` change the capability to "List, track, confirm, close, or drop open loops". · `README.md`
- [ ] T038 [P] [JR] [DOCS] `docs/architecture.md`: the `loops` row in the agent/tools table (≈ line 295) lists `list_open_loops`, `track_loop`, `confirm_loop`, `close_loop`, `drop_loop`; in the node table note that `fetch_context` detects "what's open" by E5 similarity (EN + PT) and adds the resume question about suspected loops, and that `surface_loops` skips when the turn asked what's open. `docs/cognitive-architecture.md` (worldstate paragraph ≈ lines 70–75): suspected loops reach the user through the Open loops page and a resume question; a confirm stamps them like a declaration. · those files
- [ ] T039 [P] [JR] [DOCS] `docs/eval.md` and `docs/testing.md`: add `make calibrate-open-query` (local, free; `--check-sets`, tuned sweep, one held-out verdict) beside the other calibrate targets, and note `test_open_query_holdout.py` is a slow test. `apps/ze-web/README.md` line 3: add "open loops" to the list of management pages. · those files
- [ ] T040 [P] [JR] [DOCS] `core/arbitration/ze-priority/README.md`: `TurnSurfacing` now detects "what's open" with `OpenQueryDetector`, caps the recap at 5 and the explicit answer at 10, and offers up to 3 suspected loops at resume (7-day cooldown in `push_log`). `core/cognition/ze-worldstate/README.md`: confirm stamps confidence 0.9 and a 7-day deadline; the loops agent has `confirm_loop`. · those files
- [ ] T041 [JR] [DOCS] `AGENTS.md`: phase table row 171 (one line, style of rows 168–170); layout tree under `ze_priority` is not listed, so only add `make calibrate-open-query` to "Essential commands" with its one-line comment. `specs/README.md`: add the 171 index row after 170 (status "✅ Implemented"). · those files
- [ ] T042 [ENG] [DOCS] Coverage check: `git diff main...HEAD --name-only`; confirm every public doc made stale is edited; then `rtk proxy grep -rniE "what's open|is_global_open_query|recap_mentions|confirm_loop|track_loop_succeeded|LoopReviewList|Open loops" README.md docs core/*/*/README.md apps/*/README.md` and list any hit not updated, with a reason. Set `spec.md` Status to Implemented and update `.spec-context.json` through the companion `write-context.py` hooks. · none

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → (US2 → US3) and (US4 → US6 → US5) in the ENG lane; US1 (JR-web) depends only on Phase 1 (it uses the existing REST confirm) and can run from the start; T026 (JR-data) can start immediately; T027 needs T029 for the non-`--check-sets` modes; T031 needs T026, T027, T029, T030; T033–T034 any time after Phase 1; T032 after T014 and T021; T035 after all code; Phase 12 after T035.
- US3 depends on US2 (`confirm_loop` calls the new `review.confirm_loop`).
- US5 depends on Phase 2 (`open_items_query` state key) and on US4/US6 being merged in `context.py` and `turn.py` (same files, same lane).

## Parallel Examples

- At start: ENG T001–T006 ∥ JR-web T007–T012 ∥ JR-data T026.
- In ENG: T015 ∥ T016 (different test files); T020 ∥ T022; T028's four sub-files can be written together.
- Docs: T037 ∥ T038 ∥ T039 ∥ T040.

## Implementation Strategy

MVP = Phases 1–5 (page + one confirm + chat confirm): F2 is closed for anyone who opens the page or names a loop. Then US4 (the resume question, the part D2 asked for), US6, US5, the pg check, evals, docs. Land as one floor; do not split the phase.

---

## Lanes

| Lane | Model | Tasks | Files owned (exclusive) | Order / hand-offs |
|---|---|---|---|---|
| **ENG** (lead) | Claude Sonnet | T001–T006, T013–T025, T028–T032, T035, T036, T042 | `core/cognition/ze-worldstate/ze_worldstate/{review.py, agents/tools.py, agents/agent.py}` and their tests; `core/contracts/ze-agents/ze_agents/nested_tools.py` + `tests/test_track_loop_honesty.py`; `core/arbitration/ze-priority/ze_priority/{turn.py, types.py, open_query.py, __init__.py}` + tests; `core/engine/ze-core/ze_core/orchestration/{state.py, nodes/context.py, nodes/loop_surfacing.py, nodes/memory.py, nodes/trace.py}`, `ze_core/conversation/messages/{types.py, store.py}` + tests; `apps/ze-api/ze_api/{container.py, api/schemas.py, api/messages.py}`, `apps/ze-api/tests/**` touched here; `packages/ze-client/src/generated/*`; `specs/phases/171-loop-confirmation/research.md` (Verdict) | Starts after 169 + 170 land. Integrates JR work, runs gates, asks Tally (T036), sets floor review. |
| **JR-web** | OpenCode flash | T007–T012 | `apps/ze-web/src/shared/config/{nav-routes.ts, nav-routes.test.ts}`, `apps/ze-web/src/app/router/routes.ts`, `apps/ze-web/src/pages/loops/**`, `apps/ze-web/src/widgets/loop-review/**` | Independent of ENG; may start at T001. Does **not** touch `packages/ze-client` (ENG regenerates it in T005). Reports to ENG. |
| **JR-data** | OpenCode flash | T026, T027, T033, T034 | `eval/calibration/{open_query.jsonl, open_query_holdout.jsonl, open_query.py}`, `eval/calibration/routing.jsonl`, `eval/scenarios/loops.yaml`, `Makefile` | T026 first (held-out committed before any tuning run). T027 `--check-sets` immediately; tuned/holdout modes after ENG's T029. ENG runs T031 (calibration judgment) without editing these files except via a request to JR-data. |
| **JR-docs** | OpenCode flash or Docs Steward | T037–T041 | `README.md`, `docs/architecture.md`, `docs/cognitive-architecture.md`, `docs/eval.md`, `docs/testing.md`, `apps/ze-web/README.md`, `core/arbitration/ze-priority/README.md`, `core/cognition/ze-worldstate/README.md`, `AGENTS.md`, `specs/README.md` | After T035. ENG does the coverage check (T042). |

Escalation: junior stuck → ENG lead; ENG design gap → Spec Architect (Sextant) if on the floor, else the Maestro; product question → Maestro.
