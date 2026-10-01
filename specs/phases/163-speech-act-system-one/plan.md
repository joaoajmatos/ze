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

**Storage**: None. Judgments ride the existing `MessageTrace.judgments` JSONB.

**Testing**: pytest, mocked `SystemOneClient` and `LLMClient`. Zero vendor calls.

**Constraints**: ze-memory already depends on ze-agents, which owns the Protocol — no new package edge. No `ze_core` import. Thresholds are config, never code defaults (FR-010).

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Spec-First | PASS — spec 163 + arch note O1 |
| III. Layering | PASS — gate in `ze_memory`; trace attach in `ze_core` node; Protocol from `ze_agents` |
| IV. Typed Python | PASS — frozen dataclass thresholds, dataclass decision, `get_logger` |
| V. Test Discipline | PASS — fail-first, mocked clients |
| VII. One LLM Gateway | PASS — wording still `LLMClient`; judgments use 162's OpenRouter System One |
| VIII. Pre-v1 | PASS — no shim; legacy path is the documented fail-open fallback, not a dual-write |

## Design decisions

- **Module**: `ze_memory/speech_act_gate.py` (`admission.py` already owns `AdmissionGate` for contribution admission — different concern).
- **Thresholds**: `system_one.surfaces.speech_act.{enabled, act_min_peakedness, family_min_peakedness, biography_min}`. Surface is on only if `system_one.enabled` AND surface `enabled` AND all three bars are numbers; otherwise it is off and the legacy judge runs. Shipped YAML: `enabled: false`, bars commented out, documented uncalibrated.
- **Peakedness** = Choice answer `confidence`. Missing confidence on a Choice that must clear a bar = hold.
- **Trace**: `gather_fact_proposals` appends plain dict rows to `configurable["admission_judgments"]`; `write_memory` passes a per-turn sink and extends `state["message_trace"].judgments` (record_trace runs before write_memory; the final state is what gets persisted). `consumed=True` marks the questions that decided the outcome (`speech_act` always; `family` + `biography` only when act is `fact` and bars were evaluated).
- **Unchanged**: trivial-turn regex (checked before any System One call), 148 same-turn identity skip (in `write_memory`, after the gate), contribution seam, `admit_speech_act` / `admit_family`.

## Project Structure

```text
core/cognition/ze-memory/ze_memory/speech_act_gate.py   # NEW: questions, thresholds, decide(), judge_admission()
core/cognition/ze-memory/ze_memory/extractor.py          # gather_fact_proposals gate + wording call
core/engine/ze-core/ze_core/orchestration/nodes/memory.py # sink + attach to trace
apps/ze-api/config/config.yaml                           # speech_act surface, off
```

## Risks

- Bars are uncalibrated; shipping off is the mitigation. Calibration on Ze fixtures (incl. PT) is the follow-up before enabling.
- Extra wording LLM call on admit only; holds cost zero LLM calls (net cheaper than today on most turns).
