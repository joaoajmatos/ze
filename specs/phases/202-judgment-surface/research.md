# Research: Judgment Surface

All facts below were checked against main at `5426cce1` on 2026-10-26. No item is left as NEEDS CLARIFICATION.

## R1. Where the module lives and what it is called

- **Decision**: a new module, `core/contracts/ze-agents/ze_agents/judgment.py`, beside `system_one.py`. It imports only `ze_agents.system_one` and `ze_logging`. `surface_block` and `parse_bar` move into it from `system_one.py`. `valid_noul` and `valid_choice` stay in `system_one.py`, because they validate answers, not surfaces.
- **Rationale**: ze-core, ze-skills, ze-worldstate and ze-memory already depend on ze-agents, so no new dependency edge is needed (spec Assumptions). Keeping it out of `system_one.py` leaves the client contract file unchanged, as the spec requires.
- **Alternatives considered**: putting it in `system_one.py` (that file is the client contract, which the spec freezes); putting it in ze-core (ze-skills, ze-worldstate and ze-memory cannot import ze-core).

## R2. How a surface declares its bars and extras

- **Decision**: each surface keeps its frozen config dataclass (`RoutingSurfaceConfig`, `ComplexitySurfaceConfig`, `SkillsSurfaceConfig`, `LoopGateSurfaceConfig`, `CorroborationSurfaceConfig`, `CommitmentIntakeSurfaceConfig`), with the same field names, order and defaults. Each one subclasses a new base, `SurfaceConfig`, and declares three class variables:
  - `SURFACE`: the config key (`"routing"`, …);
  - `BARS`: bar name → the question id that bar governs;
  - `EXTRAS`: extra field name → a parser for its raw config value.
  The base provides `from_settings(settings)` (the only parser), `calibrated` (enabled, every bar in `BARS` set, and `consistent()`), `consistent()` (true by default; corroboration overrides it with `corroborate_hold <= promote_hold`) and `bar_for(question_id)`.
- **Rationale**: every `decide()` takes its typed config and reads `cfg.choice_trust` and so on. Keeping the dataclasses keeps `decide()` and its tests unchanged (FR-002, FR-012, SC-005). Declaring bars and extras as data lets the shared module parse and check them, which deletes the six parsers and `_BAR_NAMES`, and gives the intake's bar map one home (it is `judgment_bars._INTAKE_BARS` today).
- **Alternatives considered**: one generic config object holding a dict of bars (would change every `decide()` signature and its tests); keeping the six `*_surface_config` functions as one-line wrappers (two names for one thing; pre-v1 hard cut says delete them).
- **Detail**: positional construction still works, because the field order is unchanged. The calibration runners stop relying on it (R13).

## R3. Splitting "may we ask?" from "ask"

- **Decision**: two functions.
  - `gate(cfg, client) -> NotAsked | None` returns `"disabled"`, `"uncalibrated"` or `"unavailable"` (no client), in that order, or `None` when the surface may ask. It logs the uncalibrated warning once (R6).
  - `judge(client, cfg, state, questions, decide, read) -> tuple[Judgment, D]` makes the single-attempt call, turns any exception into `SystemOneResult(outcome="skip", skip_reason="error")`, runs `decide(result)`, and builds the record.
- **Rationale**: the call sites do surface-specific work between the two steps: routing builds its shortlist and skips with fewer than two agents, skills builds its shortlist, the loop gate checks the provenance, complexity checks for a `model_simple` before it checks `enabled`. One function that did both would need hooks for each of these.
- **Alternatives considered**: a `Surface` object with overridable steps (a framework where two functions do).

## R4. How the module reads a decision

- **Decision**: each surface module exports `read_decision(decision) -> DecisionUse`, where `DecisionUse` holds `consumed: frozenset[str]` and `unused_reason: str | None`. `judge()` takes it as `read`.

  | Surface | `consumed` | `unused_reason` |
  |---|---|---|
  | routing | `decision.consumed` | `decision.reason` when `kind == "skip"` |
  | skills | `decision.consumed` | `decision.reason` when `kind == "skip"` |
  | complexity | `{needs_deep_reasoning}` when `decision.consumed` | `decision.decided_by` when it is `invalid_answer` |
  | loop_gate | `decision.consumed` | `decision.reason` when `kind == "fallback"` |
  | corroboration | `{same_concern}` when `kind` is `promote`, `corroborate` or `not_same` | `decision.reason` when `kind == "fallback"` |
  | commitment_intake | `outcome.consumed` | `outcome.reason` when `kind == "fallback"` |

- **Rationale**: the decision types differ (`TierDecision.consumed` is a bool, `CorroborationDecision` has no consumed set). Changing them would change decision tests (SC-005). A small reader per surface keeps them as they are.
- **Alternatives considered**: a `consumed`/`skip_reason` protocol on every decision type (edits `TierDecision` and `CorroborationDecision` and their tests).

## R5. The one meaning of `skip_reason` (FR-007)

- **Decision**: `Judgment.skip_reason` is `"error"` when `judge()` caught an exception; else `result.skip_reason` when `result.outcome == "skip"` (a skip with no reason stays `None`; real clients always set one); else `read(decision).unused_reason`. The trace-row rule is unchanged: a skip result gives one row per question with that reason; an ok result gives one row per question, carrying the reason, and a missing answer gives its own skip row.
- **Effect per surface**: routing, skills and complexity rows are the same as today. Intake rows on an exception are new (FR-006). Loop gate and corroboration log lines are the same except that an exception now logs the record (R10).
- **Spec fix**: the spec's FR-007 example listed `abstain` as a skip reason. Routing's `abstain` is a Choice held under `choice_trust`, so it is "held under a bar" and has no skip reason, as today. The spec example is corrected.

## R6. Warn once per surface per process

- **Decision**: `ze_agents.judgment` logs through two `functools.lru_cache`d helpers, `_warn_uncalibrated(surface)` and `_warn_bar_invalid(surface, bar)`. A third public function, `reset_surface_warnings()`, clears both caches for tests. The events become `system_one_surface_uncalibrated` (field `surface`) and `system_one_bar_invalid` (fields `surface`, `bar`). An exception logs `system_one_judgment_error` (fields `surface`, `error`).
- **Rationale**: SC-006 asks for once per process, and the worldstate surfaces re-parse their config on every call and hold no long-lived object for corroboration, so the state has to live at module level. AGENTS.md allows `lru_cache` singletons for exactly this kind of process state.
- **Alternatives considered**: a warned-flag on each orchestrator (what `TierJudge` does today; corroboration has no orchestrator object, and a per-instance flag is not per process); a plain module-level `set` (the convention forbids it).
- **Test impact**: tests that assert a warning call `reset_surface_warnings()` first. `test_tier_node.py:230` patches `ze_core.routing.tier.log`; it patches `ze_agents.judgment.log` instead (a patch-target edit, allowed by SC-005). The events named in `docs/configuration.md:613` change with them.

## R7. The record type and the checkpoint

- **Decision**: `Judgment` is a frozen dataclass in `ze_agents.judgment` with `surface`, `result`, `question_kinds` (a dict in question order), `consumed`, `skip_reason` and `bars` (question id → `SurfaceBar | None`). `SurfaceBar(name, value)` is a frozen dataclass. `CORE_CHECKPOINT_MODULES` (`ze_core/checkpoint_serde.py:20`) gains `ze_agents.judgment` and `ze_agents.system_one`.
- **Rationale**: `RoutingEnvelope` sits in `AgentState` and is checkpointed, and it will carry a `Judgment`, which carries a `SystemOneResult`. Today `RoutingJudgment.result` holds a `SystemOneResult`, but `ze_agents.system_one` is not in the allowlist, so a resumed turn may not rebuild it. Adding both modules and a round-trip test makes the record survive a confirmation pause.
- **Alternatives considered**: keeping the record out of the envelope (routing would need a second channel to `embed_route`).

## R8. Trace rows come from the record alone

- **Decision**: `ze_core/conversation/messages/judgments.py` replaces `judgments_from_result(...)` with `judgment_rows(judgment: Judgment) -> list[JudgmentTrace]`. It reads the surface, kinds, consumed set, skip reason and bars from the record, and turns each `SurfaceBar` into the existing `JudgmentBar`. `JudgmentTrace` and `JudgmentBar` keep their shape, so REST, the `trace_update` frame, the message store and the web trace panel do not change.
- **Rationale**: FR-005 and SC-002. ze-core keeps the trace types (spec Assumptions).

## R9. The commitment intake on an exception

- **Decision**: the intake calls `judge()`. An exception becomes a skip result; `decide()` already returns `IntakeOutcome("fallback", "error")` for it (`commitment_judge.py:260-261`). `_fallback` takes the record and puts it on `IntakeAdmission.judgment`. `write_memory` then writes six question rows with `skip_reason="error"` and the `intake_outcome` row (`fallback:error`).
- **Rationale**: FR-006 and US1 scenario 1. The Haiku fallback runs as before.

## R10. Loop gate and corroboration records

- **Decision**: both call `gate()` and `judge()`. `LoopInflow._log` logs `skip_reason` from the record when there is one, else the decision reason for a fallback. Corroboration's `_judge` returns `(judgment, decision)`.
- **Rationale**: the spec edge case: background inflows write no trace rows, but their log line uses the same record and semantics. Today an exception logs `skip_reason="error"` with no answers; it still does, now from the record.

## R11. The dead `fact_judge` path

- **Decision**: delete `write_memory`'s non-intake judgment branch (the non-intake branch of `write_memory`, at `nodes/memory.py:182-193` on `5426cce1`) and `FactAdmission.judgment`, `question_ids`, `consumed` and `skip_reason`. `intake.py` stops setting them, in `CommitmentIntake._fallback` and `_apply` (`intake.py:216`, `262-265`, `306-308` on `5426cce1`). Delete `test_fact_fallback_rows_have_fact_judge_surface_and_no_bar` (`test_judgment_bars.py:349`).
- **Rationale**: `gather_fact_proposals` returns `FactAdmission(path="none")` or `FactAdmission(facts=..., path="haiku")` only (`extractor.py:449`, `467`). No production code reads the four fields (grep, 2026-10-26). User decision, Clarifications 2026-10-26.

## R12. Complexity

- **Decision**: `choose_tier` keeps its order (`compound`, `off` with no judge, `no_simple_model`), then calls `gate(judge.surface, client)`, mapping `"disabled"` to `off` and `"uncalibrated"` to `uncalibrated`. `TierJudge.warn_uncalibrated_once` and `_uncalibrated_warned` are deleted. `TierJudge.choose` calls `judge()` and returns `TierOutcome(decision, model, judgment)`. `decide_tier` uses `valid_noul` (FR-008); its outcomes do not change, because `valid_noul` with `unit_range=True` checks the same five conditions as the inline copy (`tier.py:111-117`).

## R13. The calibration harness

- **Decision**: one new file, `eval/calibration/harness.py`, imported by the runners the way `commitment_intake.py` imports its baseline (`sys.path.insert(0, <dir>)`, `commitment_intake.py:43`). It provides:
  - rows: `load_jsonl(path, row_type)` with duplicate-id checks, `norm(text)`, `blind_overlap(a, b)`;
  - set shape: `language_counts`, `require_languages`, `shape_report(problems)` (the `check_sets` printout and exit code);
  - config: `load_config()`, `surface_config(cls, **bar_overrides)` (calls `cls.from_settings`), `parse_bar_list(text, names)` for `--bars`, `model_from_config()`;
  - live run: `run_live(client, rows, state_of, questions_of, concurrency)` → results by row id; `make_client(args)` (the `OPENROUTER_API_KEY` check and the client);
  - reports: `reliability_bins(points)` and `print_reliability`, `bar_grid(values, metric)` and `print_grid`, `print_verdict(by_language)`;
  - results: `save_results(path, results)` and `load_results(path)` for `SystemOneResult` maps;
  - CLI: `common_args(parser)` (`--check-sets`, `--set`, `--bars`, `--model`, `--timeout-ms`, `--concurrency`, `--seed`, `--save`, `--load`) and `held_out_warning()`.
  Each runner keeps its `Row` gold columns, its quotas, its scoring and `Counts`, its baseline (Haiku, E5 or the old pipeline) and its acceptance rule (FR-011).
- **Rationale**: the measured copies: `load_rows` ×7 (87 lines), `report_reliability` ×5 (114), `report_grid` ×4 (71), `check_sets` ×6 (113), `parse_bars` ×3, `config_model` ×3, `main_async` ×6 (507, mostly the same set/holdout/client plumbing), `parser` ×5 (100). These copies total 1,155 lines, so the harness cannot reach a 25% drop without touching scoring; moving them and adding the harness gives the ≥12% drop (SC-004, Clarifications 2026-10-27) with scoring untouched.
- **Production parser**: every place a runner builds a config (bars from `--bars`, the bar grid, the "no pair passes" printout) goes through `harness.surface_config`, which calls `from_settings`. This fixes `loop_gate.py:536` (R15).
- **Alternatives considered**: a package `eval/calibration/__init__.py` (the runners are scripts and the tests load them by path; a sibling import matches what already works); a runner base class (each runner's flow differs enough that functions read better).

## R14. Proving calibration is unchanged

- **Decision**: before any runner changes, the `calib` lane captures golden output from the current runners.
  - `apps/ze-api/tests/calibration/replay.py` holds a deterministic `ReplayClient` (each answer derived from a SHA-256 of the state and question id; fixed `latency_ms`), a hash embedder (unit vectors from SHA-256, for the E5 baselines and shortlists) and a fake Haiku client (for the loop-gate baseline).
  - `apps/ze-api/tests/calibration/capture_golden.py` runs each System One runner's `--check-sets` and one tuned and one held-out run (frozen bars) with those fakes patched in (`OpenRouterSystemOneClient`, `get_embedder`, the Haiku client, `OPENROUTER_API_KEY`), and writes stdout to `apps/ze-api/tests/calibration/golden/<runner>-<mode>.txt`.
  - `apps/ze-api/tests/calibration/test_calibration_golden.py` re-runs the same commands and compares output exactly.
  After the refactor the same test also runs each runner with `--save`, then `--load`, and checks the reloaded report is identical (US3 scenario 1).
- **Rationale**: only `commitment_intake.py` can save and load results today, and no saved results are in git (`eval/results/` is ignored), so "a recorded results file" has to be made. A replay client makes the live path testable offline with no credits.
- **Limits**: the golden runs cover the paths the fakes reach. The `loop_gate.py` "no bar pair passes" path raises today (R15), so it has no golden; it gets a new test after the fix.

## R15. The broken loop-gate printout

- **Decision**: fixed as a side effect of R13. The "no pair passes" path builds its display config through `harness.surface_config(LoopGateSurfaceConfig, loop_hold=0.9, resolves_hold=0.9)`. A new test forces that path with the replay client.
- **Rationale**: this is the drift FR-011 exists to stop: a runner building a config by hand that production no longer accepts.

## R16. Coordination with 203

- **Decision**: agreed with Tarn (architect, floor 203) on 2026-10-26, recorded in both plans and in the "202 Handoffs" note. 202 lands first; 203 rebases onto it. 202 owns the judgment side of the shared files and 203 the commit side (plan.md, Coordination with 203). 203 owns FR-009.
- **Rationale**: 202's edits in those files are small hunks; 203 rewrites the commit path. Rebasing 203 is cheaper than the reverse.

## R17. Crew size

- **Decision**: five lanes: `lead` (contract), `engine` (ze-core and ze-skills), `ws` (ze-worldstate and ze-memory), `calib` (eval/calibration and its tests), `docs`.
- **Rationale**: the engine nodes and the skills matcher change together (the node reads the matcher's record), so they share a lane. The worldstate files are shared with 203 and must sit in one lane. Calibration is large, separate and starts with the golden capture. Nothing is pure and test-specified enough for a Haiku JR lane except docs.
