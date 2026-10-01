# Implementation Plan: Speech-Act System One

**Branch**: `163-speech-act-system-one` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/163-speech-act-system-one/spec.md`. Depends on 162 (Implemented, `SystemOneClient` on `config["configurable"]["system_one_client"]`).

## Summary

Post-turn fact admission today asks one Haiku call for `{speech_act, family, facts[]}`. 163 moves the **judgment** to System One and keeps the **wording** in the LLM:

1. One batched System One request with three independent questions: `speech_act` Choice (eight labels), `family` Choice (five keep families + `drop`), `biography` Noul.
2. Code decides: `admit_speech_act` → must be `fact`; Choice peakedness ≥ act bar; `admit_family` → keep family with peakedness ≥ family bar; biography Noul ≥ its own bar. Anything else is a **hold** — no fact, no LLM call, no Haiku tie-break (FR-006).
3. Only on **admit** does a narrow wording call produce `facts[]` (family fixed). System One returns labels and probabilities, not text, so it cannot word a fact.
4. System One **skip** (disabled, timeout, 429/529, error) or surface off → the pre-163 extractor runs once, unchanged.

## Technical Context

**Language/Version**: Python 3.11+. No web changes (162 already renders `judgments`).

**Primary Dependencies**: Existing `ze-agents` (`SystemOneClient` Protocol), `ze-memory` (`SpeechAct`, `KEEP_FAMILIES`, `admit_*`), `ze-core` node. No new package, no new third-party dependency.

**Storage**: None. Judgments ride the existing `MessageTrace.judgments` JSONB.

**Testing**: pytest, mocked `SystemOneClient` and `LLMClient`. Zero vendor calls.

**Target Platform**: ze-api process (post-turn `write_memory` node).

**Project Type**: monorepo feature (memory gate + engine node wiring + config).

**Performance Goals**: One batched System One request per non-trivial turn (~100 ms class, 162's 2000 ms timeout). Holds add no LLM call; admits add one short wording call.

**Scale/Scope**: Single-user. One new module, two edited modules, one config block.

**Constraints**: ze-memory already depends on ze-agents, which owns the Protocol — no new package edge. No `ze_core` import. Thresholds are config, never code defaults (FR-010).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source: `.specify/memory/constitution.md`.*

| Principle | Assessment |
|---|---|
| I. Spec-First Development | PASS — phase spec + governing arch note (O1) before implement |
| II. Single-User Model | PASS — no tenant scoping; one config surface |
| III. Layered Package Architecture | PASS — gate in `ze_memory` (already depends on `ze_agents`, which owns the Protocol); trace attach in the `ze_core` node; no `ze_core` import from `ze_memory`; no new package edge |
| IV. Typed, Explicit Python | PASS — frozen dataclass thresholds, dataclass decision, `get_logger`; no Pydantic in the domain module |
| V. Test Discipline | PASS — fail-first, mocked `SystemOneClient` and `LLMClient`, no real DB, no live vendor |
| VI. Explicit Persistence | PASS — no migration; reuses `MessageTrace.judgments` JSONB from 162 |
| VII. One LLM Gateway, Local Embeddings | PASS — wording stays on `LLMClient`; judgments use 162's OpenRouter System One on the same key; E5/NLI untouched |
| VIII. Pre-v1 Hard Cuts | PASS — no dual-write: a hold never runs the legacy judge, and only a System One skip does (the documented fail-open path), so two judges never write two rows |

**Post-design re-check**: Thresholds are required config (no code defaults), so the surface cannot turn on by accident. The data model has no new table. PASS.

## Design decisions

- **Module**: `ze_memory/speech_act_gate.py` (`admission.py` already owns `AdmissionGate` for contribution admission — different concern).
- **Thresholds**: `system_one.surfaces.speech_act.{enabled, act_min_peakedness, family_min_peakedness, biography_min}`. Surface is on only if `system_one.enabled` AND surface `enabled` AND all three bars are numbers; otherwise it is off and the legacy judge runs. Shipped YAML: `enabled: false`, bars commented out, documented uncalibrated.
- **Peakedness** = Choice answer `confidence`. Missing confidence on a Choice that must clear a bar = hold.
- **Trace**: `gather_fact_proposals` appends plain dict rows to `configurable["admission_judgments"]`; `write_memory` passes a per-turn sink and extends `state["message_trace"].judgments` (record_trace runs before write_memory; the final state is what gets persisted). `consumed=True` marks the questions that decided the outcome (`speech_act` always; `family` + `biography` only when act is `fact` and bars were evaluated).
- **Unchanged**: trivial-turn regex (checked before any System One call), 148 same-turn identity skip (in `write_memory`, after the gate), contribution seam, `admit_speech_act` / `admit_family`.

## Project Structure

### Documentation (this feature)

```text
specs/phases/163-speech-act-system-one/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
├── checklists/
│   └── requirements.md
└── contracts/
    ├── speech-act-gate.md
    └── trace-judgments-admission.md
```

### Source Code (repository root)

```text
core/cognition/ze-memory/ze_memory/speech_act_gate.py   # NEW: questions, thresholds, decide(), judge_admission()
core/cognition/ze-memory/ze_memory/extractor.py          # gather_fact_proposals gate + _word_admitted_facts
core/cognition/ze-memory/tests/test_speech_act_system_one.py
core/engine/ze-core/ze_core/orchestration/nodes/memory.py # per-turn sink + attach to trace
core/engine/ze-core/tests/orchestration/nodes/test_extractor_dual_write.py
apps/ze-api/config/config.yaml                           # speech_act surface, off
specs/arch/system-one-models.md
specs/README.md
CLAUDE.md
```

**Structure Decision**: Reuse 162's client, DI, and trace type unchanged. The gate lives beside the extractor it gates, in its own module (`admission.py` already owns the unrelated `AdmissionGate`).

## Complexity Tracking

> No constitution violations.

## Risks

- Bars are uncalibrated; shipping off is the mitigation. Calibration on Ze fixtures (incl. PT) is the follow-up before enabling.
- Extra wording LLM call on admit only; holds cost zero LLM calls (net cheaper than today on most turns).
