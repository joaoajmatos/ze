# Tasks: System One Skill Gating

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V, FR-014, SC-005). Fail-first. Default suites never POST to OpenRouter. Use a fake `SystemOneClient` (async `evaluate(state, questions, *, max_attempts=None)` that records calls) and the existing `make_embedder` pattern.

**Tags**: `[BE]` backend Python · `[WEB]` ze-web · `[PLATFORM]` config / Makefile / eval tooling / spec index · `[DOCS]` docs, specs, READMEs.

**Normative references**: decision table and shortlist: [contracts/skills-judgment.md](./contracts/skills-judgment.md). Outcome type, node flow, trace: [contracts/matcher-node-trace.md](./contracts/matcher-node-trace.md).

**Ordering**: Phases run in order. `[P]` tasks touch different files and can run together.

---

## Phase 1: Setup

- [x] **T001** [P] [PLATFORM] Under `system_one.surfaces` add `skills` with `enabled: false`, `choice_trust: null`, `needs_skill_hold: null`, `shortlist_k` and `shortlist_floor` set to placeholder values (`5`, `0.35`) commented `# provisional — pick from make calibrate-skills (T034)`. Comment the two bars `# uncalibrated — set from make calibrate-skills`. · `apps/ze-api/config/config.yaml`
- [x] **T002** [P] [PLATFORM] Add the `calibrate-skills` Makefile target (`uv run python eval/calibration/skills.py`), its help line and `.PHONY` entry, mirroring `calibrate-routing`. · `Makefile`

---

## Phase 2: Foundational (blocks every story)

**Purpose**: Types, surface config, questions, shortlist, the outcome hard cut, the shared state helper. With the surface off this phase changes no behavior (SC-001).

**Wave 1 — fail-first tests (different files):**

- [x] **T003** [P] [BE] Fail-first, `skills_surface_config` and questions: missing/invalid block → disabled; enabled with a null bar → `calibrated` false; bad bars (string, NaN, >1, bool) become `None` with a warning; invalid `shortlist_k` (<1, bool, str) and `shortlist_floor` (outside 0..1) fall back to defaults; the matcher clamps a floor above `match_threshold` to it with a warning; `build_questions` yields a `choice` with the key→description criteria plus `none` and a `noul` with no criteria; descriptions are capped; duplicate slugs get `slug (source)` keys and the key map resolves to exactly one skill. · `core/automation/ze-skills/tests/test_skills_judge.py`
- [x] **T004** [P] [BE] Fail-first, `shortlist()`: skills below `shortlist_floor` are excluded, explicit-matched skills are excluded, results sort by cosine desc with a stable tie-break, `shortlist_k` caps, an empty result is returned as empty (no request). · `core/automation/ze-skills/tests/test_skills_judge.py`
- [x] **T005** [P] [BE] Fail-first, shared judgment-state helper: history hint keeps today's truncation and inactivity rule, `routing_hints` becomes `context`, caps match the 164 constants, `embed_route` output is byte-identical after the move. · `core/engine/ze-core/tests/orchestration/test_judgment_state.py`
- [x] **T006** [P] [BE] Fail-first, types: `SkillMatch.below_floor` defaults false; `SkillsJudgment` and `SkillMatchOutcome` exist; `SkillUsageTrace.below_floor` defaults false and an old stored trace without the key parses with the default. · `core/automation/ze-skills/tests/test_types.py`, `core/engine/ze-core/tests/orchestration/test_message_trace.py`

**⟶ Wait for T003–T006, then:**

- [x] **T007** [P] [BE] Add `SkillMatch.below_floor`, `SkillsJudgment`, `SkillMatchOutcome`. · `core/automation/ze-skills/ze_skills/types.py`
- [x] **T008** [P] [BE] Create `judge.py`: `SkillsSurfaceConfig`, `skills_surface_config`, `shortlist`, `build_questions`, `build_judgment_state_skills` (the `skills` line list), `SkillsDecision`, a stub `decide()` that returns skip. Local `_bar` copy (research R7). · `core/automation/ze-skills/ze_skills/judge.py`
- [x] **T009** [P] [BE] Add `SkillUsageTrace.below_floor` and parse default; copy it in `_extract_skills_used`. · `core/engine/ze-core/ze_core/conversation/messages/types.py`, `messages/store.py`, `orchestration/nodes/trace.py`
- [x] **T010** [BE] Create `judgment_state.py` (history hint + state builder) and switch `embed_route` to it; delete the private copy in `routing.py`. · `core/engine/ze-core/ze_core/orchestration/judgment_state.py`, `nodes/routing.py`
- [x] **T011** [BE] Hard-cut `SkillMatcher.match` to return `SkillMatchOutcome` (judgment always `None` for now), accept `system_one_client`, `surface` and `judgment_state`; update the existing 114 matcher tests and `test_skills_node.py` to the new return type with no behavior change. `build_skill_matcher` takes the client and builds the surface from settings. · `core/automation/ze-skills/ze_skills/matching.py`, `bootstrap.py`, `core/automation/ze-skills/tests/test_matching.py`, `test_bootstrap.py`, `core/engine/ze-core/tests/orchestration/test_skills_node.py`
- [x] **T012** [BE] `match_skills`: build the judgment state, call the new `match`, return judgments **append-only** (read `state["judgments"]`, add rows, never replace), still no-op on missing matcher or context. `container.py` passes `shared.system_one_client`; add a fail-first assertion that the built container's `skill_matcher` holds the shared client and the parsed surface. · `apps/ze-api/tests/test_agent_wiring.py` · `core/engine/ze-core/ze_core/orchestration/nodes/skills.py`, `apps/ze-api/ze_api/container.py`

**Checkpoint**: `make test-skills`, `make test-core` pass with the surface off (SC-001).

---

## Phase 3: User Story 1 — Only the skill that fits applies (P1) 🎯 MVP

**Independent Test**: Two skills above 0.5; trusted Choice for A and Noul above bar → only A applies; explicit `/slug` stacks.

- [x] **T013** [P] [US1] [BE] Fail-first, `decide()`: trusted named Choice with Noul at or above `needs_skill_hold` → apply with `consumed={skill, needs_skill}`; trusted `none` → drop with `consumed={skill}`; Noul below bar → drop; Choice key not in the shortlist or Noul missing → skip `invalid_answer`; null bar → skip `uncalibrated`; client skip → skip with its reason. · `core/automation/ze-skills/tests/test_skills_judge.py`
- [x] **T014** [P] [US1] [BE] Fail-first, matcher with fake client: two skills above `match_threshold` and a trusted Choice for A → one automatic match; `none` → no automatic match; explicit `/slug` for B plus trusted Choice for A → both; the request carries the shortlist keys, `max_attempts=1` and the bounded state; no request when the shortlist is empty; `encode_query` runs once per call (FR-012). · `core/automation/ze-skills/tests/test_matching.py`
- [x] **T015** [P] [US1] [BE] Fail-first, `match_skills`: judgment rows are appended after existing `embed_route` rows (SC-006), `skill`/`needs_skill` rows are `consumed` per outcome, `allowed-tools` is the intersection over the final set only, a dropped skill imposes no restriction. · `core/engine/ze-core/tests/orchestration/test_skills_node.py`

**⟶ Wait for T013–T015, then:**

- [x] **T016** [US1] [BE] Implement `decide()` per the contract (skip, abstain, drop, apply order). · `core/automation/ze-skills/ze_skills/judge.py`
- [x] **T017** [US1] [BE] Implement the matcher gating path: shortlist, one batched `evaluate`, `decide`, outcome → matches (explicit stack; chosen automatic skill; abstain/skip fall back to 114), exceptions caught into a skip judgment. · `core/automation/ze-skills/ze_skills/matching.py`
- [x] **T018** [US1] [BE] Node converts `outcome.judgment` with `judgments_from_result` and returns judgments even when no skill applies. · `core/engine/ze-core/ze_core/orchestration/nodes/skills.py`

**Checkpoint**: US1 independently testable with a fake client.

---

## Phase 4: User Story 2 — A skill just under the floor applies, visibly (P1)

**Independent Test**: Skill at 0.43 with trusted Choice and Noul → in `skills_used` with `below_floor`; none → not applied.

- [x] **T019** [P] [US2] [BE] Fail-first, matcher: skill between `shortlist_floor` and `match_threshold` applies on Apply and carries `below_floor=True`; unsure or `none` → not applied; skill below `shortlist_floor` never appears in the shortlist or the matches. · `core/automation/ze-skills/tests/test_matching.py`
- [x] **T020** [P] [US2] [BE] Fail-first, trace: `_extract_skills_used` copies `below_floor`; the REST/WS schema exposes `below_floor` with default false and the OpenAPI response model includes it. · `core/engine/ze-core/tests/orchestration/nodes/test_trace_skills.py`, `apps/ze-api/tests/api/test_messages_route.py`
- [x] **T021** [P] [US2] [WEB] Fail-first (vitest): `SkillsSection` renders a "below floor" mark only when `below_floor` is true and keeps the existing badges otherwise. · `apps/ze-web/src/widgets/trace-panel/ui/SkillsSection.test.tsx`

**⟶ Wait for T019–T021, then:**

- [x] **T022** [US2] [BE] Set `below_floor` in the matcher when an applied automatic skill has similarity under `match_threshold`. · `core/automation/ze-skills/ze_skills/matching.py`
- [x] **T023** [P] [US2] [BE] `SkillUsageTraceResponse.below_floor` and the messages route mapping. · `apps/ze-api/ze_api/api/schemas.py`, `apps/ze-api/ze_api/api/messages.py`
- [x] **T024** [US2] [WEB] Regenerate `@ze/client` types and add the mark to `SkillsSection.tsx`; run `make typecheck-web` and `make test-web`. · `packages/ze-client`, `apps/ze-web/src/widgets/trace-panel/ui/SkillsSection.tsx`

---

## Phase 5: User Story 3 — Off, unsure and failing paths keep 114 (P1)

**Independent Test**: The 114 matcher fixtures give identical results with the surface off, uncalibrated, skipped, invalid and unsure.

- [x] **T025** [P] [US3] [BE] Fail-first, matcher parity: surface disabled → no `evaluate` call and results equal the 114 fixtures; enabled with null bar → no call and a single warning; client skip, raised exception, malformed answer, Choice key outside the shortlist, unsure Choice → 114 result with skip/abstain judgment rows and `consumed` false; explicit-only turn with no automatic candidates makes no request. · `core/automation/ze-skills/tests/test_matching.py`
- [x] **T026** [P] [US3] [BE] Fail-first, `match_skills`: matcher exception returns `{}` as today; abstain keeps every automatic skill at or above `match_threshold`; judgment rows exist for skip and abstain. · `core/engine/ze-core/tests/orchestration/test_skills_node.py`
- [x] **T027** [US3] [BE] Implement abstain and skip fallbacks and the once-per-call uncalibrated warning in the matcher; confirm `decide()` handles every skip reason. · `core/automation/ze-skills/ze_skills/matching.py`, `judge.py`
- [x] **T028** [US3] [BE] SC-001/SC-005 and FR-007/FR-017 regression check (no change to `/slug` parsing, review, `allowed-tools`, 163 and 164 behavior): run `make test-skills`, `make test-core`, `make test` and confirm no 114 fixture changed except for the return type; grep the default suites for any live System One call. · repo

---

## Phase 6: User Story 4 — Calibration produces bars and shortlist size (P2)

**Independent Test**: Offline `--recall` prints recall at k = 3..8 with no network; dataset test validates shape.

- [ ] **T029** [P] [US4] [PLATFORM] Write `eval/calibration/skills_roster.yaml`: about 12 realistic skills (slug, name, description, source) including at least three near-miss pairs; descriptions written as a user would write them. · `eval/calibration/skills_roster.yaml`
- [ ] **T030** [P] [US4] [PLATFORM] Write `eval/calibration/skills.jsonl`: about 80 rows, ≥ 30% PT, covering clear apply, near-miss between similar skills, no-skill turns, below-floor paraphrases, explicit `/slug` and history-dependent follow-ups. · `eval/calibration/skills.jsonl`
- [ ] **T031** [P] [US4] [BE] Fail-first: dataset shape (ids unique, gold is a roster slug or `none`, band valid, language balance), and script offline mode (`--recall` prints k = 3..8 per language with a fake embedder and makes no network call; live path never imported by default). · `apps/ze-api/tests/calibration/test_skills_calibration.py`

**⟶ Wait for T029–T031, then:**

- [ ] **T032** [US4] [PLATFORM] Write `eval/calibration/skills.py`: roster load, production `shortlist()` with the real E5 singleton, live System One run with shuffled option order, report Choice accuracy and a peakedness reliability table, `none` precision/recall, Noul separation (apply vs no-skill rows), a `choice_trust` × `needs_skill_hold` grid with wrong-skill applies and missed applies, gold recall at k = 3..8 and floors 0.30..0.45 per language, and suggested values. `--recall` runs offline. Never collected by pytest. · `eval/calibration/skills.py`
- [ ] **T033** [US4] [PLATFORM] Run `--recall` offline against the roster and record the table in `research.md` under R1. Re-read the 164 tuning findings first (ask Keel on the 164 Tuning floor for anything newer than commit `43f9c652`: recall at k=4/5, whether `shortlist_k` default moved, whether live bars were set) and note what changed. · `specs/phases/166-skill-suggestion-system-one/research.md`
- [ ] **T034** [US4] [PLATFORM] Pick `shortlist_k` and `shortlist_floor` from the T033 table (smallest values reaching the recall target in both languages), set them in `config.yaml` and as the code defaults in `judge.py`, and update the spec Clarifications tuning note. Bars stay `null`. · `apps/ze-api/config/config.yaml`, `core/automation/ze-skills/ze_skills/judge.py`, `spec.md`
- [ ] **T035** [US4] [PLATFORM] (Out-of-band, needs credits) Run `make calibrate-skills` once; if a safe pair of bars exists, set them and enable the surface; if not, leave `null` and record the finding as 164 did. Not required for Implemented status. · `apps/ze-api/config/config.yaml`

---

## Phase 7: Polish and Docs

- [ ] **T036** [P] [BE] `make lint` and `make format`; `make typecheck-web`; `graphify update .`. · repo
- [ ] **T037** [P] [DOCS] `docs/skills.md`: Matching section covers the shortlist, the Choice/Noul gate, the one-automatic-skill rule (a deliberate narrowing of 114, with explicit still stacking), the below-floor mark, fail-open, and the config block; correct the "existing routing embedding" wording. · `docs/skills.md`
- [ ] **T038** [P] [DOCS] `docs/configuration.md`: `system_one.surfaces.skills` keys (including `shortlist_k`, `shortlist_floor`), calibration command, and a cross-link from the `skills:` block. · `docs/configuration.md`
- [ ] **T039** [P] [DOCS] `core/automation/ze-skills/README.md`: matcher, judge module and surface. · `core/automation/ze-skills/README.md`
- [ ] **T040** [P] [DOCS] `specs/arch/system-one-models.md`: O3 row to a specified and implemented note with implementation notes (pre-floor, one winner, k from data), Sequencing and Appendix A rows, fix the status line (162–164 Implemented, 163/164 uncalibrated unless T035 changes it). · `specs/arch/system-one-models.md`
- [ ] **T041** [P] [DOCS] `specs/core/ze-core.md` (graph-side glue and shared state helper) and `specs/phases/114-agent-skills/spec.md` (add a pointer under FR-019 to 166's narrowing; do not rewrite 114 history). · `specs/core/ze-core.md`, `specs/phases/114-agent-skills/spec.md`
- [ ] **T042** [P] [DOCS] `AGENTS.md` phase table row 166; `specs/README.md` index row 166 (number 166, never 165); set spec Status to Implemented when done. · `AGENTS.md`, `specs/README.md`
- [ ] **T043** [P] [DOCS] Root `README.md` has no skills mention: confirm nothing there describes automatic skill matching and record "no change needed" in the PR notes; add a line only if a features list names skills. · `README.md`
- [ ] **T044** [DOCS] Coverage check: run `git diff main...HEAD --name-only` and confirm every public doc touched or implied (`docs/skills.md`, `docs/configuration.md`, ze-skills README, the ADR, `specs/core/ze-core.md`, AGENTS.md, `specs/README.md`, and README or an explicit no-change note) is in the diff; list any code change (config keys, trace field, Makefile target) with no doc. · repo

---

## Dependencies & Order

- Setup (T001–T002) first, in parallel.
- Foundational blocks all stories; within it, tests T003–T006 → implementation T007–T012.
- US1 (T013–T018) is the MVP; US2 depends on US1's matcher path (T022 after T017); US3 and US4 can start after Foundational, US3 completes after US1.
- T033–T034 need T032; T034 needs T033. T035 is optional and out-of-band.
- Docs T037–T043 after behavior is stable; T044 last.

## Handoff note for implementers

Tags split cleanly: `[BE]` ze-skills + ze-core + ze-api; `[WEB]` T021, T024 only; `[PLATFORM]` config, Makefile, eval; `[DOCS]` Phase 7. Order: Foundational, US1, US2, US3, US4, Polish.
