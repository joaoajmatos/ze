# Tasks: Routing Choice After E5

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V, FR-010, SC-005). Write them fail-first. Default suites never POST to OpenRouter. Use a fake `SystemOneClient` (an object with async `evaluate(state, questions, *, max_attempts=None)` that records calls) and the existing `make_embedder` pattern. Mock `client.complete` for Haiku.

**Tags**: `[BE]` backend Python · `[PLATFORM]` config / Makefile / eval tooling · `[DOCS]` docs, specs, AGENTS.md · `[WEB]` none in this phase (research R9: `JudgmentsSection` and `RoutingBadge` need no change).

**Normative references**:
- decision table: research.md R2;
- question set, state and config: [contracts/routing-judgment.md](./contracts/routing-judgment.md);
- factory and both call sites: [contracts/router-factory.md](./contracts/router-factory.md);
- envelope, confidence and trace rows: [contracts/envelope-judgments.md](./contracts/envelope-judgments.md).

---

## Phase 1: Setup

**Purpose**: Default-off surface config.

- [x] **T001** [P] [PLATFORM] Under the existing `system_one.surfaces`, add `routing` with `enabled: false`, `choice_trust: null`, `multi_specialist_hold: null`, `complexity_lookup_max: null`, `shortlist_k: 4`. Comment the three bars `# uncalibrated — set from make calibrate-routing`. · `apps/ze-api/config/config.yaml`

---

## Phase 2: Foundational

**Purpose**: Types, surface config, questions, the single router factory (production drift hard cut), and the `judgments_from_result` kind fix. With the surface off this phase changes no routing behavior (SC-004). It blocks every story.

**⚠️** Start no user-story work until this phase is complete.

**Wave 1 — fail-first tests (different files):**

- [x] **T002** [P] [BE] Fail-first, `judgments_from_result(result, *, question_kinds, consumed, skip_reason=None)`:
  - a skip result with `question_kinds={"agent":"choice","multi_specialist":"noul","complexity":"score"}` yields three rows whose `kind` matches the map (the Score row is `score`);
  - an ok result missing the Score answer yields a `score` row with `skip_reason` set;
  - an ok Score answer yields `answer=<float>`, `peakedness=None`, `probabilities=None`;
  - the 163 `biography` noul and `speech_act`/`family` choice rows still convert correctly through the map.

  · `core/engine/ze-core/tests/conversation/test_judgments.py`
- [x] **T003** [P] [BE] Fail-first, router factory:
  - `build_embedding_router` gives `RouterConfig.threshold`/`gap_threshold` from YAML `routing:` and the 160 defaults when absent;
  - `models.overrides.<agent>` changes the model `_resolve_model` returns;
  - `models.overrides.router_fallback` (or `models.default`) sets `fallback_model`;
  - the injected `SystemOneClient` and `routing_surface_config` are on the router;
  - `bootstrap.build_router(stack, settings)` and the base `Container.build` step 9 both go through the factory (patch the factory and assert it is called once, with the client).

  · `core/engine/ze-core/tests/routing/test_router_factory.py`
- [x] **T004** [P] [BE] Fail-first, `routing_surface_config` and questions:
  - missing/invalid block → disabled; `enabled: true` with a null bar → `calibrated` false;
  - bad bars (string, NaN, >1) become `None` with a warning; `shortlist_k` invalid or <2 → 4;
  - `build_questions(shortlist)` has `agent` (choice, criteria = shortlist names → descriptions, plus `none`), `multi_specialist` (noul), `complexity` (score, three ordered levels);
  - `shortlist(ranked, k)` returns the top-k, clamps to the enabled count and never returns fewer than two when two exist;
  - `build_state` caps `user` at 2000 chars and `context` at 600, drops empty `history`/`context`.

  · `core/engine/ze-core/tests/routing/test_routing_judge.py`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — implementation:**

- [x] **T005** [P] [BE] Hard-cut `judgments_from_result`: replace `question_ids` with `question_kinds: Mapping[str, str]`, derive skip/missing-row `kind` from it, delete `_skipped_kind`. Update the 163 caller to pass `{qid: SPEECH_ACT_QUESTIONS[qid].type for qid in admission.question_ids}` and fix `test_memory_judgments.py`/`test_trace_judgments.py` call sites. · `core/engine/ze-core/ze_core/conversation/messages/judgments.py`, `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`
- [x] **T006** [P] [BE] Add `RoutingJudgment` and the `RoutingEnvelope` fields `judgment: RoutingJudgment | None = None` and `complexity_source: str = "regex"` per data-model.md. · `core/engine/ze-core/ze_core/routing/types.py`
- [x] **T007** [P] [BE] Create `judge.py` with `RoutingSurfaceConfig`, `routing_surface_config(settings)`, `build_questions(shortlist)`, `build_state(user, history, context)`, `shortlist(ranked_agents, k)` (top-k, clamped to the enabled count, minimum 2) and `RoutingDecision` (no `decide()` yet; T014 introduces it). · `core/engine/ze-core/ze_core/routing/judge.py`

**⟶ Wait for T006 and T007, then:**

- [x] **T008** [BE] Create `factory.py` (`router_config_from`, `build_embedding_router`) per the contract. `EmbeddingRouter.__init__` gains `system_one_client` and `surface` and stores them; no behavior change yet. Export from `routing/__init__.py`. · `core/engine/ze-core/ze_core/routing/factory.py`, `core/engine/ze-core/ze_core/routing/router.py`, `core/engine/ze-core/ze_core/routing/__init__.py`
- [x] **T009** [P] [BE] `bootstrap.build_router(stack, settings)` calls the factory with `stack.system_one_client`; update the caller. Delete the `RouterConfig()`-only construction. · `core/engine/ze-core/ze_core/bootstrap.py`, `apps/ze-api/ze_api/container.py`
- [x] **T010** [P] [BE] Base `Container.build` step 9: build a `SystemOneClient` with `build_system_one_client(settings)`, register it in `deps`, and replace the inline `RouterConfig(...)`/`EmbeddingRouter(...)` with the factory call. Delete the inline blocks. · `core/engine/ze-core/ze_core/container.py`

**Checkpoint**: Run `make test-core test`. SC-004: with the surface off the existing routing tests (`test_router.py`, `test_router_integration.py`, `test_e5_routing_confidence.py`, `test_haiku_fallback.py`, `test_nodes.py`) pass unchanged.

---

## Phase 3: User Story 1 — A clear single job still skips the fallback planner (P1) 🎯 MVP

**Goal**: With a calibrated surface and a fake Choice that agrees, 160 clear singles (EN + PT) stay non-compound, decompose is not called, and the visible confidence is the Choice peakedness.

**Independent Test**: `make test-core` router and node tests with a fake client.

- [x] **T011** [P] [US1] [BE] Fail-first, `decide()` trust and skip rows: Choice agent ≥ `choice_trust` with Noul below the bar → `trust` (consumed `agent`, `multi_specialist`); client skip → `skip` with the client reason; missing/unknown Choice or null confidence → `skip` `invalid_answer`; bars never read the Noul for the Choice and vice versa. · `core/engine/ze-core/tests/routing/test_routing_judge.py`
- [x] **T012** [P] [US1] [BE] Fail-first, router (`EmbeddingRouter` + fake client + `make_embedder`):
  - 160 clear calendar EN and PT with Choice = calendar at high peakedness → `is_compound` false, `routing_method` `embedding`, `confidence` = peakedness, `raw_scores` cosine, `score_gap` cosine gap;
  - the fake saw exactly one `evaluate` call with `max_attempts=1`, a shortlist of at most `shortlist_k` agents plus `none`, and a state that keeps `user` separate from `history`;
  - skip (`DisabledSystemOneClient`, null bar, surface off, `judgment_state=None`) → envelope field-for-field equal to the 160 result (SC-004);
  - single enabled agent → no `evaluate` call;
  - a client that raises is treated as skip.

  · `core/engine/ze-core/tests/routing/test_router_choice.py`
- [x] **T013** [P] [US1] [BE] Fail-first, `embed_route`:
  - passes `judgment_state` with `user` equal to the raw prompt (or image caption) and `history` equal to the existing hint, while the E5 text stays combined as today;
  - returns `state["judgments"]` rows converted from `envelope.judgment` with the right `consumed` flags;
  - sets the telemetry agent context to `router` around the router call.

  · `core/engine/ze-core/tests/orchestration/nodes/test_routing_nodes.py`

**⟶ Wait for T011–T013, then:**

- [x] **T014** [US1] [BE] Implement `decide()` for skip, invalid and trust per research R2 (pure; no I/O; never raises). · `core/engine/ze-core/ze_core/routing/judge.py`
- [x] **T015** [US1] [BE] Implement the Choice flow in `EmbeddingRouter._score_and_route`: build the shortlist (top `shortlist_k`, clamped), call `evaluate(state, questions, max_attempts=1)` inside try/except (exception → skip `error`), run `decide`, and build the envelope per the contract (trust: `is_compound=False`, `primary_agent` = Choice agent, `confidence` = peakedness; log `routing_choice_disagrees_e5` on mismatch; set `envelope.judgment`). No call when the surface is not calibrated, `judgment_state` is `None`, or fewer than two agents. · `core/engine/ze-core/ze_core/routing/router.py`
- [x] **T016** [US1] [BE] `embed_route`: build `judgment_state` from the raw prompt/caption, the history hint and `routing_hints`; pass it to `router.route`; convert `envelope.judgment` with `judgments_from_result(question_kinds=…, consumed=…)`; return `{"envelope": envelope, "judgments": rows}`; wrap with `set_agent_context("router")`. · `core/engine/ze-core/ze_core/orchestration/nodes/routing.py`

**Checkpoint**: US1 tests pass; `make test-core` still passes. Clear singles skip decompose with a Choice; skip equals 160.

---

## Phase 4: User Story 2 — Close scores can still be one specialist (P1)

**Goal**: A close-gap (or low-top) turn goes to one specialist when the Choice is confident; `none` still decomposes even when cosine looked clear; unsure falls back to the 160 bars.

**Independent Test**: Router fixtures with a fake Choice.

- [x] **T017** [P] [US2] [BE] Fail-first:
  - cosine gap below `ROUTING_GAP_THRESHOLD` and Choice = agent A at high peakedness → `is_compound` false (SC-002);
  - cosine top below `ROUTING_THRESHOLD` and Choice confident → `is_compound` false (Clarification Q2);
  - Choice `none` at high or low peakedness with a clear cosine top → `is_compound` true, `confidence` = peakedness, `primary_agent` = E5 top;
  - Choice below `choice_trust` → abstain: the 160 bars decide both ways (clear top stays single; close gap stays compound), `confidence` cosine, Choice row unused;
  - Choice picks a different shortlist agent than the E5 top → `primary_agent` = Choice agent and the disagreement log fires;
  - `decide()` rows for `choice_none` and `choice_unsure`.

  · `core/engine/ze-core/tests/routing/test_router_choice.py`, `core/engine/ze-core/tests/routing/test_routing_judge.py`
- [x] **T018** [US2] [BE] Implement `decide()` `none` → `decompose`, unsure → `abstain`; ensure the router skips the 160 bar test on `trust` and uses it unchanged on `abstain`/`skip`; the decompose envelope keeps the E5 top as `primary_agent` and sets `confidence` to the Choice peakedness. · `core/engine/ze-core/ze_core/routing/judge.py`, `core/engine/ze-core/ze_core/routing/router.py`

**Checkpoint**: US1 + US2 tests pass.

---

## Phase 5: User Story 3 — Real mixed work still decomposes; Score only picks the tier (P1)

**Goal**: A high multiple-specialist Noul or `none` decomposes; 153/155 rewrite is untouched; the complexity Score changes only the model tier.

**Independent Test**: Router + node tests; existing 153/155 tests unchanged.

- [x] **T019** [P] [US3] [BE] Fail-first:
  - Choice agent ≥ `choice_trust` with Noul ≥ `multi_specialist_hold` → `is_compound` true (consumed `agent`, `multi_specialist`); Noul below the bar → single; Noul is not read when the Choice is `none` or unsure;
  - Score valid and `complexity_lookup_max` set: score at or below → `complexity="simple"`, above → `"complex"`, `complexity_source="score"`, same `primary_agent` as without a Score (US3 AC3); bar null or Score missing → regex complexity and the Score row unused;
  - `decompose` node: an incoming envelope with `complexity_source="score"` keeps its complexity for the primary subtask and `_resolve_model` still sets subtask models; `"regex"` still calls `classify`; a mixed gather+act Haiku result still comes out companion-primary with the conductor hint (the existing `apply_conductor_rewrite` tests in `test_nodes.py` pass unchanged).

  · `core/engine/ze-core/tests/routing/test_router_choice.py`, `core/engine/ze-core/tests/orchestration/nodes/test_routing_nodes.py`
- [x] **T020** [US3] [BE] Implement `decide()` Noul gate and Score mapping per research R2/R6; thread `complexity` and `complexity_source` into the envelope for trust, decompose and abstain outcomes when the Score is consumed. · `core/engine/ze-core/ze_core/routing/judge.py`, `core/engine/ze-core/ze_core/routing/router.py`
- [x] **T021** [US3] [BE] `decompose` node: when the incoming envelope has `complexity_source == "score"`, keep its complexity for the new envelope's primary subtask instead of calling `classify`; set `new_envelope.complexity_source` accordingly. Do not touch `apply_conductor_rewrite`. · `core/engine/ze-core/ze_core/orchestration/nodes/routing.py`
- [x] **T022** [US3] [BE] SC-003 check: run `make test-core` and confirm `test_nodes.py` conductor rewrite cases and the 153/155 tests pass with no edits to their expectations.

**Checkpoint**: US1–US3 tests pass. The surface is still off in committed config.

---

## Phase 6: Calibration

**Purpose**: Measure the three bars and ship the labeled set. Depends only on T007 (questions and shortlist helper).

- [ ] **T023** [P] [PLATFORM] Create `eval/calibration/routing.jsonl`. Each row: `{id, lang, prompt, history?, gold_agent | "none", gold_multi: bool, gold_complexity: lookup|single_tool|multi_hop}`. Cover EN and PT clear singles per agent in the checked-in roster, close-gap singles, `none` rows (off-roster asks), mixed gather+act and sequential rows, and each complexity level. · `eval/calibration/routing.jsonl`
- [ ] **T024** [P] [BE] Dataset shape test: every row parses, `lang` ∈ {en, pt}, gold agents exist in the registry or equal `none`, both languages cover every complexity level, at least one `none` and one mixed row per language. · `core/engine/ze-core/tests/routing/test_calibration_dataset.py`
- [ ] **T025** [P] [PLATFORM] Create `eval/calibration/routing.py` (opt-in live; never collected by pytest). It builds the production shortlist with the local E5 singleton, asks the production questions with option order shuffled (eval only), then prints Choice accuracy vs gold, a peakedness reliability table, `none` precision/recall, Noul separation for gold mixed vs single, Score separation by level, a grid of `choice_trust`/`multi_specialist_hold` with the 160 false-compound count each would remove, and suggested values for the three bars. · `eval/calibration/routing.py`
- [ ] **T026** [P] [PLATFORM] Add the `calibrate-routing` Makefile target, `.PHONY` entry and `make help` line ("LIVE System One run over eval/calibration/routing.jsonl; costs credits"). · `Makefile`

---

## Phase 7: Polish & Cross-Cutting

- [ ] **T027** [P] [DOCS] Document `system_one.surfaces.routing` keys: off by default, three separate uncalibrated bars, `shortlist_k`, the calibration command, and that `routing_log.confidence` is the Choice peakedness when `method=embedding` and a Choice was consumed. Follow the `doc-style` skill. · `docs/configuration.md`
- [ ] **T028** [P] [DOCS] Document the routing judgment and the single router factory (and that both call sites use it). · `specs/core/ze-core.md`
- [ ] **T029** [P] [DOCS] Mark sequencing step 3 / O2 as Implemented, set Appendix A rows for `EmbeddingRouter`, `ComplexityEstimator` and Haiku `decompose`, and add notes under O2 (single attempt, bars, drift fix, Score mapping). · `specs/arch/system-one-models.md`
- [ ] **T030** [P] [DOCS] Update the 164 phase-table row to Implemented with the one-line scope. · `AGENTS.md`
- [ ] **T031** [BE] Run `make test-agents test-core test-memory test lint`. SC-005: confirm every new test injects a fake `SystemOneClient` and none constructs `OpenRouterSystemOneClient` against a real transport. Fix any failures. · repo root
- [ ] **T032** [DOCS] Set spec `**Status**:` to Implemented. · `specs/phases/164-routing-choice-after-e5/spec.md`

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T010)** → user stories.
- Wave 2 order: T005, T006, T007 in parallel; then T008; then T009 and T010 in parallel (both need T008).
- **US1 (T011–T016)** is the MVP and lands first: it creates the Choice path in `_score_and_route` that US2 and US3 extend. T014 → T015 → T016.
- **US2 (T017–T018)** and **US3 (T019–T022)** both depend on US1. They touch `judge.py` and `router.py`, so serialize T018 and T020.
- **Calibration (T023–T026)** depends only on T007 and can run beside the stories.
- **Polish (T027–T032)**: docs run after the stories. T031 runs before T032.

## Parallel Examples

- Foundational Wave 1: T002, T003, T004 together.
- Foundational Wave 2: T005, T006, T007 together; then T009 with T010.
- US1 tests: T011, T012, T013 together.
- Calibration T023–T026 beside any story phase.
- Polish docs T027–T030 together.

## Implementation Strategy

1. Do Setup and Foundational first. The factory hard cut and the kind fix ship with zero routing behavior change (SC-004), which is a safe stopping point and fixes the production drift on its own.
2. Do US1 next as the MVP. With a calibrated config clear singles get an honest confidence and still skip Haiku.
3. Then US2 (fewer false compounds), then US3 (mixed work and the Score tier).
4. A maintainer runs calibration once to set the bars. The surface stays `enabled: false` in committed config until the user decides to turn it on.
5. Finally Polish: docs, AGENTS.md and status.

Commit split by user story when asked: Foundational, US1, US2, US3, Calibration, Docs.
