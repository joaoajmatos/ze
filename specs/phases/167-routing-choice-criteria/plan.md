# Implementation Plan: Routing Choice Criteria

**Branch**: `164-research-routing` (floor branch) | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/167-routing-choice-criteria/spec.md` (clarified 2026-10-12). Governing: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) O2.

## Summary

Phase 164's routing Choice is confident and wrong on explain / compare / how-to questions. Three causes, three changes:

1. **Contradictory description** → delete "explain X" from companion's `description`.
2. **Bare Choice wording** → optional `routing_criteria` class attribute on `BaseAgent` (use-for / not-for text for the Choice only), stronger generic Choice instructions and `none` criterion. `build_questions` stays plugin-agnostic: it receives a `name → criterion` mapping.
3. **Weak shortlist** → an offline recall gate over three calibration sets picks `shortlist_k` (smallest k with recall ≥ 0.95 on all three; may be the whole roster).

Then the user runs the live calibration on the two held-out sets. The surface is enabled only if the acceptance rule holds; otherwise the phase closes as option F (surface off, documented). The implementer also prepares an opt-in script that shows what companion does with research prompts.

E5 passages stay the `description` text (the scratch experiment shows description edits do not move recall).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Existing only (`ze_agents`, `ze_core.routing`, `OpenRouterSystemOneClient`). No new packages.

**Storage**: None. No migration. Trace judgments already carry the question text.

**Testing**: pytest, fake `SystemOneClient`, `make test-core`, `make test-agents`, `make test-personal`. Calibration scripts are opt-in and never collected.

**Project Type**: Backend + eval tooling. No web change.

**Constraints**:
- Dependency graph: `routing_criteria` lives on `BaseAgent` in `ze-agents` (contracts); `ze-core` reads it through the agent registry. `ze_core` names no plugin agent. Plugins set the attribute on their own agents.
- Pre-v1 hard cut: no shim. `build_questions` changes signature; the one production caller (`router.py`) and the calibration script are updated in the same change.
- Calibration must exercise the production question builder (one shared criterion lookup), otherwise calibrated bars do not transfer.
- FR-013: on skip, behavior equals 164. The 160 bars, `decompose`, 153/155 do not change.
- `routing_holdout2.jsonl` is never used to tune wording (FR-010).

**Scale/Scope**: 10-agent roster; one System One request per multi-agent turn when enabled.

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Spec-First Development | PASS — spec clarified before code |
| II. Single-User Model | PASS — n/a |
| III. Layered Package Architecture | PASS — attribute on `ze-agents` (contracts), consumer in `ze-core` (engine), values in `ze-personal`; no upward or plugin→core import |
| IV. Typed, Explicit Python | PASS — `routing_criteria: str = ""`; helper returns `dict[str, str]` |
| V. Test Discipline | PASS — fake client; dataset test covers `holdout2`; no live calls in default tests |
| VI. Explicit Persistence | PASS — no persistence change |
| VII. One LLM Gateway, Local Embeddings | PASS — System One stays on `/systemone`; E5 unchanged |
| VIII. Pre-v1 Hard Cuts | PASS — `build_questions` signature replaced, no dual path |

Post-design re-check: PASS (see `research.md` R2 for why a field beats a `judge.py` table).

## Project Structure

### Documentation

```text
specs/phases/167-routing-choice-criteria/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md  tasks.md
└── checklists/requirements.md
```

### Source touched

```text
core/contracts/ze-agents/ze_agents/base_agent.py      # routing_criteria: str = ""
core/engine/ze-core/ze_core/routing/judge.py          # instructions, none criterion, build_questions(criteria), criterion_for()
core/engine/ze-core/ze_core/routing/router.py         # pass criteria (routing_criteria or description)
plugins/ze-personal/ze_personal/agents/companion/agent.py  # description drops "explain X"; routing_criteria
plugins/ze-personal/ze_personal/agents/research/agent.py   # routing_criteria
eval/calibration/routing.py                           # multi-set, per-set/lang report, research->companion misses, k sweep to roster size, criteria via shared helper
eval/calibration/routing_holdout2.jsonl               # DONE (spec author)
eval/calibration/companion_research_check.py          # new, opt-in, --live required
apps/ze-api/config/config.yaml                        # shortlist_k, and enabled/bars only if accepted
core/engine/ze-core/tests/routing/                    # judge, router, dataset, calibration-script tests
core/contracts/ze-agents/tests/                       # routing_criteria default
docs/configuration.md  specs/arch/system-one-models.md  specs/phases/164-.../spec.md  AGENTS.md  specs/README.md
```

**Structure Decision**: Option 1 of research R2 (field on `BaseAgent`).

## Phases

### Phase A — Offline gate (free, first)
Extend the recall command to all three sets and k up to the roster size. Record the smallest passing k. If none passes → option F, skip B–D live work (still do the description fix and docs).

### Phase B — Criteria
Field, builder, instructions, `none` criterion, companion + research criteria and description fix. Unit tests with the fake client prove: the criterion text reaches the question, fallback to description, no plugin name in `judge.py`, companion description has no "explain".

### Phase C — Calibration tooling and live check script
Multi-set report with the acceptance verdict printed (pass/fail per rule). `companion_research_check.py`.

### Phase D — User runs live calibration
Handoff stops here. The user runs `routing.py` on both held-out sets (and `routing.jsonl` for tuning) and the companion check. The implementer then sets config and docs from the printed result (enable, or option F).

## Complexity Tracking

| Item | Why |
|---|---|
| `shortlist_k` may equal the roster | Recall data (spec, research R3) shows k=6 cannot pass; whole-roster Choice is affordable at 10 agents. Flagged to the user as a deviation |
