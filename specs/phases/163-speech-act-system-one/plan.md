# Implementation Plan: Speech-Act System One

**Branch**: `163-speech-act-system-one` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/163-speech-act-system-one/spec.md` (clarified 2026-10-08). Governing: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) O1.

## Summary

Post-turn fact admission (`gather_fact_proposals` → `write_memory`) stops asking Haiku to *judge* every non-trivial turn. When `system_one.surfaces.speech_act` is enabled and both hold bars are set, one batched System One request asks three questions over `{user, assistant[:1000]}`:
- a Choice over the eight `SpeechAct` labels,
- a Choice over `KEEP_FAMILIES ∪ {drop}`,
- a Noul: "durable biography about the user?"

Pure code then decides **persist / hold / skip**:
- **Persist** calls a narrowed Haiku *value writer* that returns fact text only. The family is the one System One chose.
- **Hold** writes nothing and makes no generative call.
- **Skip** (disabled, unset bar, missing key, timeout, overload, error, invalid request) runs the pre-163 Haiku judge once.

The speech-act call makes a single attempt, through a new per-call `max_attempts` on `SystemOneClient.evaluate`. Judgments land on `MessageTrace.judgments` because `write_memory` returns an updated `message_trace`. A calibration set (EN+PT JSONL) and an opt-in live script produce the hold bars. The surface ships off.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Existing only. `SystemOneClient` (162, `ze_agents.system_one`), `OpenRouterSystemOneClient` (162, `ze_core.openrouter.system_one`), `LLMClient.complete` for Haiku. No new packages.

**Storage**: Nothing new and no migration. `messages.trace` JSONB already holds `judgments` (162).

**Testing**: pytest with a mocked `SystemOneClient` and a mocked `client.complete`. Runs under `make test-memory`, `make test-core` and `make test-agents`. The calibration script is opt-in and default pytest never collects it.

**Target Platform**: ze-api process (graph `write_memory` node).

**Project Type**: monorepo backend change across contracts (ze-agents), cognition (ze-memory), engine (ze-core), config (ze-api) and eval data.

**Performance Goals**: The speech-act System One call is a single attempt bounded by `system_one.timeout_ms` (2000 ms default), with no retry sleeps. Hold turns make zero generative calls (SC-006).

**Constraints**:
- Principle VII: the value writer and the Haiku fallback stay on `LLMClient`. System One stays on `/systemone`.
- FR-003: closed sets are unchanged. `admit_speech_act` and `admit_family` remain the only label filters.
- FR-005: minimal state.
- FR-006: no double judge.
- FR-013: the `eval-` skip is untouched.
- Dependency graph: ze-memory MUST NOT import ze-core, so trace conversion lives in ze-core.

**Scale/Scope**: Single user; one request per non-trivial, non-eval turn when enabled.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source: `.specify/memory/constitution.md`.*

| Principle | Assessment |
|---|---|
| I. Spec-First Development | PASS — 163 spec clarified; ADR O1 governs |
| II. Single-User Model | PASS — no tenant scoping; same key |
| III. Layered Package Architecture | PASS — judge in ze-memory (depends on ze-agents for the Protocol); `JudgmentTrace` conversion in ze-core; no ze-memory → ze-core import; no plugin change |
| IV. Typed, Explicit Python | PASS — dataclasses (`SpeechActSurfaceConfig`, `AdmissionDecision`, `FactAdmission`); `get_logger`; fail-open returns rather than raising |
| V. Test Discipline | PASS — mocked client + mocked `complete`; calibration script outside pytest collection; SC-005 asserted |
| VI. Explicit Persistence | PASS — no schema change |
| VII. One LLM Gateway, Local Embeddings | PASS — generative calls (value writer, fallback) go through `LLMClient`; judgments go through OpenRouter System One; no new key |
| VIII. Pre-v1 Hard Cuts | PASS — `gather_fact_proposals` return type hard-cut to `FactAdmission` (all callers updated); `evaluate` gains a `max_attempts` keyword in the Protocol and both implementations; no shim, no dual judge |

**Post-design re-check**:
- The decision function is pure and owns all thresholds (pinned #2, #7, #8).
- The Noul bar and the Choice bar are separate config keys (FR-002).
- Skip runs exactly one Haiku judge; hold runs none (FR-006).
- Default config is disabled with null bars, so SC-007 sees zero behavior change.

PASS.

## Project Structure

### Documentation (this feature)

```text
specs/phases/163-speech-act-system-one/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── speech-act-judgment.md      # questions, state, decision table, config
│   ├── fact-admission.md           # gather_fact_proposals return + write_memory/trace
│   └── system-one-max-attempts.md  # evaluate(..., max_attempts=) delta to 162
├── checklists/requirements.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
core/contracts/ze-agents/ze_agents/system_one.py               # Protocol: max_attempts kw
core/contracts/ze-agents/tests/test_system_one.py
core/engine/ze-core/ze_core/openrouter/system_one.py           # honor max_attempts (Disabled + OpenRouter)
core/engine/ze-core/tests/openrouter/test_system_one.py
core/cognition/ze-memory/ze_memory/speech_act_judge.py         # NEW: questions, state, surface config, decide()
core/cognition/ze-memory/ze_memory/extractor.py                # gather_fact_proposals → FactAdmission; value writer
core/cognition/ze-memory/ze_memory/types.py                    # FactAdmission dataclass
core/cognition/ze-memory/ze_memory/__init__.py                 # export FactAdmission
core/cognition/ze-memory/tests/fixtures/speech_act_gold.py     # NEW: gold fake answers (EN+PT)
core/cognition/ze-memory/tests/test_speech_act_judge.py        # NEW: decide() table, questions, config
core/cognition/ze-memory/tests/test_speech_act_system_one.py   # NEW: gather_fact_proposals paths with fakes
core/engine/ze-core/ze_core/conversation/messages/judgments.py # NEW: SystemOneResult → list[JudgmentTrace]
core/engine/ze-core/ze_core/orchestration/nodes/memory.py      # consume FactAdmission; return message_trace
core/engine/ze-core/tests/conversation/test_judgments.py       # NEW
core/engine/ze-core/tests/orchestration/nodes/test_memory.py
core/engine/ze-core/tests/orchestration/nodes/test_extractor_dual_write.py
core/engine/ze-core/tests/orchestration/nodes/test_memory_judgments.py  # NEW
apps/ze-api/config/config.yaml                                 # system_one.surfaces.speech_act
eval/calibration/speech_act.jsonl                              # NEW: labeled EN+PT set
eval/calibration/speech_act.py                                 # NEW: opt-in live calibration
Makefile                                                       # calibrate-speech-act target
specs/arch/system-one-models.md                                # sequencing → 163 status
specs/core/ze-memory.md                                        # admission judge section
docs/configuration.md                                          # system_one.surfaces.speech_act keys
AGENTS.md                                                      # phase table row 163
```

**Structure Decision**: The judge is admission policy, so it lives beside `admit_speech_act` in ze-memory. It is typed against the ze-agents Protocol, the same pattern ze-memory uses for `NLIClient`. The engine converts results into `JudgmentTrace` because that type belongs to ze-core. There is no web change: `JudgmentsSection` (162) already renders judgments from the persisted trace and the final `trace_update` frame.

## Complexity Tracking

> No constitution violations.
