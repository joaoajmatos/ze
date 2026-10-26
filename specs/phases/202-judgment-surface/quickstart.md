# Quickstart: verify phase 202

Everything here runs offline: no OpenRouter credits, no database. Run from the repo root.

## 1. Unit gates per package

```bash
make test-agents        # ze_agents.judgment: gate, judge, from_settings, warn-once, record
make test-core          # judgment_rows, the four nodes, router, tier, checkpoint round trip
make test-skills
make test-worldstate
make test-memory
make test               # ze-api tests, including apps/ze-api/tests/calibration
make lint
```

(Short names: see `docs/testing.md`. `make test-py` runs them all.)

## 2. US1: an attempted judgment always shows on the trace

`core/engine/ze-core/tests/orchestration/nodes/test_judgment_surface_errors.py` (T020) makes the fake System One client raise, one surface at a time, and asserts:

| Surface | Rows | `skip_reason` | Extra |
|---|---|---|---|
| routing | `agent`, `multi_specialist` | `error` | bars `choice_trust`, `multi_specialist_hold` |
| skills | `skill`, `needs_skill` | `error` | bars `choice_trust`, `needs_skill_hold` |
| complexity | `needs_deep_reasoning` | `error` | bar `simple_max` |
| commitment intake | the six intake questions | `error` | the six holds, plus the `intake_outcome` row `fallback:error`; Haiku fallback still runs |

A timeout result (`SystemOneResult(outcome="skip", skip_reason="timeout")`) keeps `timeout` on every row. An enabled, uncalibrated surface makes no request, writes no row and logs `system_one_surface_uncalibrated` once across two turns.

```bash
uv run pytest core/engine/ze-core/tests/orchestration/nodes/test_judgment_surface_errors.py -q
```

## 3. US2: a new surface is questions, state, bars and decide

`core/contracts/ze-agents/tests/test_judgment.py` (T003) declares a test surface with two Nouls and two bars, judges it against a fake client and checks the record. `core/engine/ze-core/tests/conversation/test_judgments.py` (T006) turns that record into rows with no bar map.

## 4. US3: calibration is unchanged

```bash
make calibrate-routing ARGS=--check-sets
make calibrate-complexity ARGS=--check-sets
make calibrate-commitment-intake ARGS=--check-sets
uv run pytest apps/ze-api/tests/calibration/test_calibration_golden.py -q
wc -l eval/calibration/*.py     # baseline 4,838; target at most 3,628 (−25%), harness included
```

The golden test compares every captured mode (see [contracts/calibration-harness.md](contracts/calibration-harness.md#golden-checks)) byte for byte, then runs `--save`/`--load` and checks the reloaded report matches.

## 5. Structural checks (SC-003, SC-004, FR-004, FR-005)

```bash
rg -n "surface_block\(" --type py core apps eval     # only ze_agents/judgment.py
rg -n "RoutingJudgment|SkillsJudgment|judgment_bars|bar_map|intake_bars|judgments_from_result|_surface_config\(" --type py core apps eval   # no hits
rg -n "def (load_rows|_norm|report_reliability|report_grid|save_results|load_results|parse_bars|config_model|system_one_config|config_system_one)\b" eval/calibration   # no hits outside harness.py
rg -n "SurfaceConfig\(" eval/calibration             # no direct construction
```

## 6. Behaviour unchanged (FR-012)

The surface decision tests (`test_routing_judge.py`, `test_tier.py`, `test_skills_judge.py`, `test_loop_judge.py`, `test_corroboration_judge.py`, `test_commitment_judge.py`) pass with only construction, import and patch-target edits. Check with:

```bash
git diff main...HEAD -- '*test_*judge*.py' '*test_tier.py' | rg '^[-+].*(assert|==)'   # review: no expected value changed
```
