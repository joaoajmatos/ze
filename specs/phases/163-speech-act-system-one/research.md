# Research: Speech-Act System One

**Feature**: `163-speech-act-system-one`
**Date**: 2026-10-01

## 1. System One judges; the LLM only words

**Decision:** System One decides admit/hold. When it admits, a narrow LLM call words the fact with the family already fixed. A hold makes no LLM call.

**Rationale:** Jev returns labels and probabilities, never text, so it cannot produce `facts[].value`. This is the arch note's cascade shape "4 + 1 (wording)": System One routes, an LLM generates. Holds are the common case (most turns state no durable fact), so the net LLM spend drops versus one Haiku call per turn.

**Alternatives considered:**
- Keep the full Haiku judge and use System One as a veto. Rejected: leaves the unreliable judge in charge of the label and keeps the per-turn LLM cost.
- Have System One return the fact text via a Score/Choice trick. Rejected: not what the primitives do.

## 2. Hold never falls back to Haiku

**Decision:** Low peakedness, even biography Noul, unknown label, or non-keep family → persist nothing and do not run the legacy judge (FR-006). Only a System One **skip** (disabled, timeout, 429/529, error, invalid request) runs the legacy extractor, once.

**Rationale:** Running Haiku to "break the tie" reintroduces the judge being replaced and risks two judges writing two rows. Doctrine: a silent wrong admit is worse than a missing fact.

## 3. Three questions in one batched request

**Decision:** `speech_act` Choice (eight labels), `family` Choice (five keep families + `drop`), `biography` Noul, sent as one request.

**Rationale:** Arch pin 7: one narrow question each, batch independent questions. Separate thresholds per question (pin 7: never transplant a Noul threshold onto a Choice). Option order is stable (`SpeechAct` enum order, then `KEEP_FAMILIES` order + `drop`).

## 4. Thresholds are config, uncalibrated, and required

**Decision:** `system_one.surfaces.speech_act.{enabled, act_min_peakedness, family_min_peakedness, biography_min}`. The surface is on only when `system_one.enabled`, the surface flag, and all three numbers are present. Otherwise the legacy judge runs. The shipped YAML has the surface off with the bars commented out.

**Rationale:** FR-010 forbids cookbook numbers as production defaults. Requiring explicit numbers means nobody enables the surface by accident with guessed bars.

## 5. Judgments reach the trace through `write_memory`

**Decision:** `gather_fact_proposals` appends plain dict rows to a per-turn sink at `configurable["admission_judgments"]`. `write_memory` creates the sink and extends `state["message_trace"].judgments`.

**Rationale:** `record_trace` runs before `write_memory` in the graph, and the final state's `message_trace` is what gets persisted. `ze_memory` cannot import `ze_core`'s `JudgmentTrace`, so it emits plain rows with the same fields. Existing fake extractors that ignore the sink keep working.

## 6. Module name

**Decision:** `ze_memory/speech_act_gate.py`.

**Rationale:** `ze_memory/admission.py` already exists (`AdmissionGate` for contribution admission, a different concern).

## Open (not this phase)

- Calibrating the three bars on Ze fixtures including Portuguese (T009).
- Measuring disagreement between post-turn act and in-turn companion tools (arch open question).
