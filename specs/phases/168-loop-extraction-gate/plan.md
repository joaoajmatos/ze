# Implementation Plan: Loop Extraction Gate (System One)

**Branch**: `168-loop-extraction-gate` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/168-loop-extraction-gate/spec.md` (clarified 2026-10-12). Governing: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) O4.

## Summary

Extraction today is one Haiku call with five fields. The plan splits it:

1. **Gate (System One, cheap)**: `ze_worldstate/loop_judge.py` defines three Noul questions, the surface config and a pure `decide()` (table in `contracts/loop-gate-judgment.md`). One batched request, `max_attempts=1`.
2. **Writer (Haiku, only after a positive gate)**: a narrow title writer returns `title` and an optional `implied_window_days`.
3. **Everything else stays in code and unchanged**: matching, dismissal fingerprints, confidence, provenance, drift arithmetic, collision detection, contribution seam.
4. **Fallback**: off, uncalibrated, skip, invalid or missing answer → the existing 109 Haiku gate, untouched.

Wiring:
- A new `LoopInflow` (`ze_worldstate/admission.py`) owns the gate and the commit, built once by ze-api with constructor-injected stores, client, `SystemOneClient` and settings. `propose_loop_candidates` takes an optional pre-made `LoopAdmission` so the conversation path judges once in the node and commits later.
- Conversation: `write_memory` awaits `loop_admission(...)` beside `fact_extractor` (run concurrently with it), appends its rows to `MessageTrace.judgments`, then `fire_and_forget`s `admission.commit()`. The worldstate `conversation_memory_hook` is deleted from the container's `memory_hooks` (hard cut). The generic `memory_hooks` mechanism stays.
- Email, calendar, ingestion: the existing `make_loop_extractor*` callables now carry the client and settings, judge inside, and log only.

Calibration: tuned set + the already-committed held-out set, a live script with a Haiku baseline, a verdict on the held-out set, an offline `--check-sets`. The surface ships off with null bars; it is switched on in the shipped config only if the verdict is `ENABLE` for EN and PT.

## Technical Context

**Language/Version**: Python 3.11+. No TypeScript.

**Primary Dependencies**: Existing only. `SystemOneClient` types from `ze_agents.system_one` (ze-worldstate already depends on ze-agents). `is_trivial_turn` from `ze_memory.extractor` (ze-worldstate already depends on ze-memory). `judgments_from_result` stays in ze-core. No new packages, no new package edge.

**Storage**: No migration. `messages.trace.judgments` already holds rows (162). `OpenLoop` and `open_loops` are untouched.

**Testing**: pytest with a fake `SystemOneClient`, a call-counting fake `LLMClient`, existing `_empty_deps()` helpers. Suites: `make test-worldstate`, `make test-core`, `make test` (ze-api), `make lint`. Live calibration is opt-in and never collected.

**Target Platform**: `write_memory` graph node; background extractors for email, calendar, ingestion.

**Performance Goals**: Conversation gate is one request, single attempt, bounded by `system_one.timeout_ms` (2000 ms), run concurrently with the 163 request so `write_memory` latency does not add. No request on trivial turns. No Haiku call on holds.

**Constraints**:
- Principle VII: System One on `/systemone`; Haiku writer through `LLMClient`.
- Dependency graph: `ze_core` stays unaware of `ze_worldstate` (the node duck-types the admission, as `match_skills` does for skills). Plugins untouched; they receive an opaque callable.
- Pin 6: named fields only; capped text; no assistant reply or session state.
- Pin 7: three independent questions, three separate bars.
- Pin 8: Noul never licenses claim kind; `explicit_declaration` only on conversation.
- FR-012: any failure yields the Haiku gate.

**Scale/Scope**: Single user; one gate request per qualifying turn or inbound item.

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Spec-First Development | PASS — spec clarified, ADR O4 governs |
| II. Single-User Model | PASS |
| III. Layered Package Architecture | PASS — judge in ze-worldstate; row conversion in ze-core; no `ze_core` import from ze-worldstate or plugins |
| IV. Typed, Explicit Python | PASS — dataclasses (`LoopGateSurfaceConfig`, `LoopGateDecision`, `LoopAdmission`, `TitleWriterResult`); `get_logger`; typed fail-open returns |
| V. Test Discipline | PASS — fake client; no live call in default suites (FR-014); calibration outside pytest |
| VI. Explicit Persistence | PASS — no schema change |
| VII. One LLM Gateway, Local Embeddings | PASS — judgments via OpenRouter System One; Haiku via `LLMClient`; E5 untouched |
| VIII. Pre-v1 Hard Cuts | PASS — worldstate conversation hook deleted in the same change; `propose_loop_candidates` signature changes at all callers in one step. One recorded asymmetry (Haiku fallback still honors explicit on non-conversation) is named for a follow-up cut |

**Post-design re-check**: `decide()` is pure and owns every bar. Three bars, three keys. Default config off with null bars; fallback equals today. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/phases/168-loop-extraction-gate/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── loop-gate-judgment.md     # questions, state shapes, decision table, config, writer
│   └── node-and-inflow.md        # LoopAdmission, node flow, trace rows, extractor wiring
├── checklists/requirements.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
core/cognition/ze-worldstate/ze_worldstate/loop_judge.py       # NEW: questions, state builders+caps, surface config, decide()
core/cognition/ze-worldstate/ze_worldstate/admission.py        # NEW: LoopInflow (gate + commit), LoopAdmission, title writer
core/cognition/ze-worldstate/ze_worldstate/extraction.py       # propose_loop_candidates(admission=...), writer, Haiku gate kept as fallback
core/cognition/ze-worldstate/ze_worldstate/inflow.py           # delete conversation_memory_hook; factories take client+settings
core/cognition/ze-worldstate/ze_worldstate/types.py            # LoopAdmission / decision types (or admission.py)
core/cognition/ze-worldstate/README.md                         # gate + surface
core/engine/ze-core/ze_core/orchestration/nodes/memory.py      # await loop_admission beside fact_extractor, merge rows, fire-and-forget commit
apps/ze-api/ze_api/container.py                                # build LoopInflow; add "loop_admission" to _build_config; drop hook; pass client+settings to extractor factories
core/ops/ze-seed/ze_seed/__main__.py                           # no change expected (uses build_container); verify with graphify
apps/ze-api/config/config.yaml                                 # system_one.surfaces.loop_gate (off, null bars)
core/cognition/ze-worldstate/tests/test_loop_judge.py          # NEW: decide() table, questions, state caps, config
core/cognition/ze-worldstate/tests/test_admission.py           # NEW: gate+commit, fallback, title writer, per-provenance
core/cognition/ze-worldstate/tests/test_extraction.py          # 109 fixtures unchanged in outcome (fallback)
core/engine/ze-core/tests/orchestration/test_loop_admission_node.py  # NEW: rows appended, trivial skip, eval/retry guard
apps/ze-api/tests/calibration/test_loop_gate_calibration.py    # NEW: dataset shape, held-out disjoint, --check-sets
eval/calibration/loop_gate.jsonl                               # NEW: tuned rows (>= 40 per language)
eval/calibration/loop_gate_holdout.jsonl                       # DONE (f2758964): 48 held-out rows, never tuned on
eval/calibration/loop_gate.py                                  # NEW: live (System One + Haiku baseline), verdict, --check-sets
Makefile                                                       # calibrate-loop-gate (+ help line, .PHONY)
specs/arch/system-one-models.md, specs/core/ (worldstate/ze-core if listed)
docs/system-one.md, docs/configuration.md, docs/cognitive-architecture.md, docs/architecture.md, docs/ingestion.md,
docs/diagrams/root/open-loops.*, README.md, AGENTS.md, specs/README.md
```

**Structure Decision**: The judge is loop-domain policy, so it lives in `ze-worldstate` and is typed against the `ze_agents` Protocol, exactly as 163 keeps `speech_act_judge` in ze-memory. `ze-core` keeps only the node glue and trace conversion; the node reaches the inflow through a duck-typed `loop_admission` in `configurable`, mirroring `fact_extractor`.

## Complexity Tracking

> No constitution violations. Accepted duplication: the bar validator exists in ze-memory, ze-skills and ze-core routing; ze-worldstate gets a fourth local copy rather than widening a shared module in this phase (same call 166 made).
