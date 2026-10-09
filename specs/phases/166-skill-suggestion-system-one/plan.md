# Implementation Plan: System One Skill Gating

**Branch**: `166-skill-suggestion-system-one` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/166-skill-suggestion-system-one/spec.md` (clarified 2026-10-09). Governing: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) O3.

## Summary

`SkillMatcher` keeps E5 and the per-skill passage cache. When `system_one.surfaces.skills` is enabled and calibrated, each turn with a non-empty shortlist sends one batched System One request (`max_attempts=1`) over a bounded state with two questions:
- a Choice over the shortlist (active, non-explicit skills at or above `shortlist_floor`, at most `shortlist_k`) plus `none`;
- a Noul `needs_skill`.

Pure code decides **apply / drop / abstain / skip** (decision table in `contracts/skills-judgment.md`):
- **Apply**: Choice names a skill at or above `choice_trust` and the Noul is at or above `needs_skill_hold`. Exactly one automatic skill applies, possibly below `match_threshold` (marked on the trace).
- **Drop**: trusted `none`, or Noul below its bar. No automatic skill.
- **Abstain**: Choice peakedness below `choice_trust`. The 114 result applies.
- **Skip**: surface off, null bar, client skip, invalid answer. The 114 result applies.

Explicit `/skill-name` skills bypass the judgment and stack. `allowed-tools` intersection runs over the final set unchanged.

Hard cuts that ride along (no shims):
- `SkillMatcher.match` returns a `SkillMatchOutcome` (matches plus an optional judgment) instead of a bare list. The one caller (`match_skills`) and all matcher tests change.
- `_history_hint` and the judgment-state build move out of `nodes/routing.py` into one shared helper used by `embed_route` and `match_skills`.
- `SkillUsageTrace` and `SkillMatch` gain `below_floor`, carried to the trace panel.

A calibration set (EN+PT JSONL), a fixed roster fixture and an opt-in live script produce the bars and the shortlist size. The script also has an offline recall-only mode. The surface ships off with null bars.

## Technical Context

**Language/Version**: Python 3.11+ (TypeScript for one trace-panel label)

**Primary Dependencies**: Existing only. `SystemOneClient` types from `ze_agents.system_one` (ze-skills already depends on ze-agents). `judgments_from_result` stays in ze-core. No new packages.

**Storage**: No migration. `messages.trace.judgments` already holds rows (162). `skills_used` is JSON inside the trace; the new `below_floor` key defaults to false when absent.

**Testing**: pytest with a fake `SystemOneClient` and the existing `make_embedder` pattern. Runs under `make test-skills`, `make test-core`, `make test` (ze-api). The live calibration is opt-in and never collected.

**Target Platform**: `match_skills` graph node (after `fetch_context`), trace panel.

**Project Type**: Backend change in `core/automation/ze-skills` and `core/engine/ze-core`, wiring in `apps/ze-api`, one `ze-web` label, config, eval data and docs.

**Performance Goals**: At most one request per turn, single attempt, bounded by `system_one.timeout_ms` (2000 ms), no retry sleeps. No request when the shortlist is empty. Skills are few, so the passage cache stays.

**Constraints**:
- Principle VII: System One stays on `/systemone`; E5 encoding unchanged.
- FR-007: `/skill-name`, review gate, `allowed-tools` intersection, scripts unchanged.
- FR-013: any failure yields the 114 result.
- Pin 6: named fields only; skill bodies never leave the process, only names and capped descriptions.
- Dependency graph: `ze-skills` imports `ze_agents` only; `ze_core` stays unaware of `ze_skills` (duck-typed outcome, as for `SkillMatch` today).

**Scale/Scope**: Single user; a handful to a few dozen skills.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Spec-First Development | PASS — 166 spec clarified; ADR O3 governs |
| II. Single-User Model | PASS |
| III. Layered Package Architecture | PASS — judge in ze-skills, row conversion in ze-core, no plugin or `ze_core` import from ze-skills |
| IV. Typed, Explicit Python | PASS — dataclasses (`SkillsSurfaceConfig`, `SkillsDecision`, `SkillsJudgment`, `SkillMatchOutcome`); `get_logger`; fail-open returns |
| V. Test Discipline | PASS — fake client; no live call in default suites (SC-005); calibration outside pytest |
| VI. Explicit Persistence | PASS — no schema change |
| VII. One LLM Gateway, Local Embeddings | PASS — judgments via OpenRouter System One; E5 untouched |
| VIII. Pre-v1 Hard Cuts | PASS — `match` return type and `_history_hint` location change in one step; no shim |

**Post-design re-check**: `decide()` is pure and owns every bar (pin 2). Choice and Noul bars are separate keys (pin 7). Skip equals 114 (SC-001). Default config is off with null bars. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/phases/166-skill-suggestion-system-one/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── skills-judgment.md      # questions, state, decision table, config, shortlist
│   └── matcher-node-trace.md   # outcome type, node flow, judgment rows, below_floor
├── checklists/requirements.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
core/automation/ze-skills/ze_skills/judge.py                 # NEW: surface config, questions, state keys, shortlist(), decide()
core/automation/ze-skills/ze_skills/matching.py              # shortlist + judge path, SkillMatchOutcome, fail-open
core/automation/ze-skills/ze_skills/types.py                 # SkillMatch.below_floor, SkillsJudgment, SkillMatchOutcome
core/automation/ze-skills/ze_skills/bootstrap.py             # build_skill_matcher(+ system_one_client, surface)
core/automation/ze-skills/README.md                          # matching + surface
core/engine/ze-core/ze_core/orchestration/nodes/skills.py    # build state, call match, append judgment rows
core/engine/ze-core/ze_core/orchestration/judgment_state.py  # NEW: history hint + state builder shared with embed_route
core/engine/ze-core/ze_core/orchestration/nodes/routing.py   # use shared helper
core/engine/ze-core/ze_core/orchestration/nodes/trace.py     # below_floor on SkillUsageTrace
core/engine/ze-core/ze_core/conversation/messages/types.py   # SkillUsageTrace.below_floor
core/engine/ze-core/ze_core/conversation/messages/store.py   # _parse_trace default
apps/ze-api/ze_api/container.py                              # pass system_one_client to build_skill_matcher
apps/ze-api/ze_api/api/schemas.py, messages.py               # below_floor on SkillUsageTraceResponse
apps/ze-api/config/config.yaml                               # system_one.surfaces.skills
apps/ze-web/src/widgets/trace-panel/ui/SkillsSection.tsx     # below-floor mark
packages/ze-client                                           # regenerated types
core/automation/ze-skills/tests/test_skills_judge.py         # NEW: decide() table, questions, config, shortlist
core/automation/ze-skills/tests/test_matching.py             # 114 fixtures on the new outcome type + gating cases
core/engine/ze-core/tests/orchestration/test_skills_node.py  # append-only judgments, outcome handling
apps/ze-api/tests/calibration/test_skills_calibration.py     # NEW: dataset shape, script offline mode
eval/calibration/skills.jsonl                                # NEW: ~80 labeled EN+PT rows
eval/calibration/skills_roster.yaml                          # NEW: fixed roster fixture
eval/calibration/skills.py                                   # NEW: live + offline --recall
Makefile                                                     # calibrate-skills
specs/arch/system-one-models.md, specs/core/ze-core.md       # O3 row, status, graph glue
docs/skills.md, docs/configuration.md, AGENTS.md, specs/README.md
```

**Structure Decision**: The judge is skill policy, so it lives in `ze-skills` beside the matcher and is typed against the `ze_agents` Protocol. `ze-core` keeps only graph-side glue and trace conversion, exactly the 163 split. The shared state helper removes a private function from `routing.py` rather than copying it.

## Complexity Tracking

> No constitution violations. One accepted duplication: the 8-line bar validator exists in `ze_core/routing/judge.py` and `ze_memory/speech_act_judge.py` already; ze-skills gets a third local copy rather than widening `ze-agents` in this phase (research R7).
