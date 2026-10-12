# Tasks: Routing Choice Criteria

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V, FR-012). Fake `SystemOneClient`; no vendor calls in default suites.

**Tags**: `[BE]` Python · `[PLATFORM]` config / eval tooling · `[DOCS]` docs and specs · `[WEB]` none in this phase.

**Rules for the implementer**
- NEVER tune criteria, instructions or k against `eval/calibration/routing_holdout2.jsonl`. Tune on `routing.jsonl` only. The holdouts are pass/fail checks (FR-010).
- NEVER run a live calibration or the companion check. The user runs them (Phase 4 is a handoff gate; there is no `[x]` for it until the user pastes results).
- Do not edit gold labels. A gold change is a user decision.
- Pre-v1 hard cut: change `build_questions` and all its callers in one change; no shim.

## Phase 1: Offline recall gate (free) — blocks everything else

- [ ] T001 [PLATFORM] [US2] Extend `eval/calibration/routing.py`: `RECALL_KS` runs from 2 up to the roster size; `--recall` accepts several `--dataset` values (`action="append"`) and prints one table per set plus a combined "smallest k with recall >= 0.95 on every set" line (or "none"). Test in `core/engine/ze-core/tests/routing/test_calibration_script.py`.
- [ ] T002 [PLATFORM] [US2] Run the offline sweep on `routing.jsonl`, `routing_holdout.jsonl`, `routing_holdout2.jsonl` (free: `--recall`). Record the table and the smallest passing k in `specs/phases/167-routing-choice-criteria/research.md` R3 (replace "today that is 9 of 10" with the measured value).
- [ ] T003 [PLATFORM] [US2] GATE: if no k up to the roster size reaches 0.95 on all three sets, STOP the live path: set `blocked`, report to the user, close as option F (T040 branch). Otherwise carry the chosen k into T031.

## Phase 2: Criteria field and builder [US1]

**Goal**: the Choice sees agent lanes in use-for / not-for form; companion no longer claims explanations.

- [ ] T010 [P] [BE] [US1] Test first in `core/contracts/ze-agents/tests/`: `BaseAgent.routing_criteria` defaults to `""`; an `@agent` without it registers fine.
- [ ] T011 [BE] [US1] Add `routing_criteria: str = ""` beside `description` in `core/contracts/ze-agents/ze_agents/base_agent.py` (~line 139). No registry change.
- [ ] T012 [P] [BE] [US1] Tests first in `core/engine/ze-core/tests/routing/test_routing_judge.py`: `build_questions({name: text})` puts each text in the Choice criteria in order and adds `none`; `criterion_for` returns `routing_criteria` when set, else `description`; no plugin agent name appears in `judge.py` (grep-style assertion over the module source for `companion|research|calendar|messenger`).
- [ ] T013 [BE] [US1] In `core/engine/ze-core/ze_core/routing/judge.py`: add `criterion_for(agent_cls)`; keep `build_questions(criteria: Mapping[str, str])`; rewrite `_AGENT_INSTRUCTIONS` per research R4 (prefer the agent that searches the web or uses tools over one answering from its own knowledge when the request needs facts, comparisons, recent information or step-by-step help; no agent names); rewrite `_NONE_CRITERION` per FR-004 (no agent can do it alone, capability does not exist, more than one agent needed; name-free examples).
- [ ] T014 [BE] [US1] Update `core/engine/ze-core/ze_core/routing/router.py` (~line 146): build the mapping with `criterion_for`. E5 passage stays `description` (`_load_agent_embeddings`). Router test in `tests/routing/test_router_choice.py`: the question sent to the fake client carries the criterion text, and the recorded judgment keeps the same question shape as 164 (FR-014).
- [ ] T015 [BE] [US1] Edit `plugins/ze-personal/ze_personal/agents/companion/agent.py`: remove `"explain X",` from `description`; add `routing_criteria` (use for: chat, emotion, reasoning about the user's own situation, multi-specialist conducting, memory/biography questions; not for: anything needing facts from the web, comparisons, how-to, recent events — those go to the web-search agent even if companion could answer from memory). Name agents by role words, not by tool lists.
- [ ] T016 [BE] [US1] Edit `plugins/ze-personal/ze_personal/agents/research/agent.py`: add `routing_criteria` (use for: explain, compare, how-to, recent events, "what is X", technical facts; not for: calendar, email, reminders, the user's own feelings or decisions). Keep `description` as is.
- [ ] T017 [P] [BE] [US1] Test in `plugins/ze-personal/tests/agents/`: companion `description` contains no `explain`; research `routing_criteria` is non-empty; the five other `@agent`s with `intents` still register.
- [ ] T018 [BE] [US1] Tune wording against `routing.jsonl` ONLY (offline reasoning plus the user's live run later). Do not read `routing_holdout2.jsonl` outputs while editing text.

**Checkpoint**: `make test-core test-agents test-personal` green; skip path identical to 164 (existing 164 router tests unchanged and passing).

## Phase 3: Calibration tooling [US3]

**Goal**: one live run prints a verdict the user can trust and act on.

- [ ] T020 [P] [PLATFORM] [US3] Tests first in `core/engine/ze-core/tests/routing/test_calibration_script.py`: multi-set report prints per-set, per-language accuracy; ECE; a research→companion miss count per candidate `choice_trust`; a PASS/FAIL line per acceptance rule (>= 0.95 EN and PT per set, ECE <= 0.10, zero research→companion misses).
- [ ] T021 [PLATFORM] [US3] Refactor `eval/calibration/routing.py`: `load_roster()` returns description AND criterion per agent (via `criterion_for`); `shuffled_questions`/`run_rows` build questions with the criterion, so calibration equals production. E5 ranking keeps using descriptions.
- [ ] T022 [PLATFORM] [US3] Accept repeated `--dataset`; run each set; print the per-set report and a final acceptance verdict for each grid `choice_trust`, plus the suggested `choice_trust`/`multi_specialist_hold` only from sets that pass. Keep `--seed`, `--k` flags.
- [ ] T023 [P] [PLATFORM] [US3] Extend `core/engine/ze-core/tests/routing/test_calibration_dataset.py` to also validate `routing_holdout.jsonl` and `routing_holdout2.jsonl` (unique ids, valid fields, gold agents in the roster or `none`, EN/PT pairs, mixed rows only with `gold_multi`).
- [ ] T024 [P] [PLATFORM] [US4] Create `eval/calibration/companion_research_check.py`: opt-in; exits with a message and no network call unless `--live`; runs the 6 research prompts of `routing_holdout.jsonl` through the real companion (reuse the eval/graph entry point used by `eval/run.py`), prints a table: prompt id, delegated to research (yes/no), LLM call count, cost, wall time, cited sources (yes/no). Test: without `--live` it exits non-zero, makes no call (patched client asserts untouched).
- [ ] T025 [PLATFORM] [US3] Add a `make` target note only if needed: `calibrate-routing` stays; document multi-set invocation in `quickstart.md`.

## Phase 4: Hand-off gate (the user runs live)

- [ ] T030 [PLATFORM] Write the implementer hand-off into the floor note: exact commands from `quickstart.md`, expected output blocks, cost estimate, and what to paste back. Set floor status `blocked` until the user pastes results.
- [ ] T031 [PLATFORM] [US2] Set `system_one.surfaces.routing.shortlist_k` in `apps/ze-api/config/config.yaml` to the k from T002/T003 (comment with the recall table and date).

## Phase 5: Enable or close (after the user's results)

- [ ] T040 [PLATFORM] [US3] If the verdict is PASS on both held-out sets: set `enabled: true`, `choice_trust`, `multi_specialist_hold`, `complexity_lookup_max` from the printed suggestion, with a dated comment (figures, set sizes). If FAIL (or T003 stopped): option F. Keep `enabled: false` and null bars, replace the comment with the dated measured figures and "calibrated, not enabled".
- [ ] T041 [BE] [US3] Add a config test (`tests/routing/test_routing_judge.py`): shipped `config.yaml` either has `enabled: false`, or `enabled: true` with non-null bars (no half-enabled state).

## Phase 6: Docs (part of done)

- [ ] T050 [P] [DOCS] Update `docs/configuration.md` routing section (lines ~351–395): `shortlist_k` meaning and chosen value, `routing_criteria` (what it is, fallback to description), the enabled or "calibrated, not enabled" state with figures.
- [ ] T051 [P] [DOCS] Update `specs/arch/system-one-models.md` O2 implementation notes (line ~73) and the O2 table row (~85): criteria field, k outcome, acceptance rule, final state.
- [ ] T052 [P] [DOCS] Add a dated status note to `specs/phases/164-routing-choice-after-e5/spec.md` (Implemented, surface state per 167).
- [ ] T053 [P] [DOCS] `AGENTS.md`: phase row 167 in the Phase status table; add `routing_criteria` to the ze-agents `base_agent.py` layout comment; mention `routing_holdout2.jsonl` and the companion check only if the layout lists calibration files. `specs/README.md`: index row 167 and Status.
- [ ] T054 [P] [DOCS] Check `README.md:48` (routing/System One paragraph), `docs/adding-an-agent.md` (document the optional `routing_criteria` attribute), and any doc quoting the companion description (`grep -rn "explain X" docs README.md plugins/*/README.md`) and update each.
- [ ] T056 [P] [DOCS] Update pinned rule 3 in `specs/arch/system-one-models.md` (line ~43, "Local E5 stays the shortlist"): state that when the recall gate needs the whole roster, E5 no longer filters for the Choice and remains only the 160 cosine skip path; cite the 167 recall table. Do this before T055.
- [ ] T055 [DOCS] Coverage check: list `git diff main...HEAD --name-only`, and for each changed behavior or file confirm a doc or spec line covers it; report gaps and fix. Set `spec.md` Status to Implemented (or "Implemented — surface off (option F)").

## Dependencies

- Phase 1 blocks all. T003 can end the live path.
- Phase 2 and Phase 3 can overlap after Phase 1 (different files), except T021 needs T013.
- Phase 4 needs Phases 2–3. Phase 5 needs the user's results. Phase 6 needs Phase 5 (T050–T052 need the final state; T053–T054 can start earlier).

## Implementation strategy

MVP = Phase 1 + Phase 2 (the description fix and criteria already change behavior with the surface off or on). The live gate decides whether it ships enabled.
