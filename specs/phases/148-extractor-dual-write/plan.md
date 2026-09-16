# Implementation Plan: Extractor Dual-Write and Dedup Races

**Branch**: `148-extractor-dual-write` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/148-extractor-dual-write/spec.md`

## Summary

A successful in-turn `remember_fact` already writes the biography fact. Post-turn extraction can still propose the same identity and persist a second current row. Close that race in `write_memory`: drop extractor proposals whose identity matches a `remember_fact` whose payload `ok` is true. Keep LLM `speech_act` admission. Tests that the model claimed remember without `ok` stay Phase 143 reply-honesty cases; this phase’s tests assert store cardinality, not wording.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Existing `write_memory`, `gather_fact_proposals` / `extract_facts`, `submit_perception_facts`, companion `remember_fact` (unchanged catalog)

**Storage**: No new tables. Current vs retracted remains `memory_facts.contradicted`

**Testing**: pytest; mock LLM and store; no real OpenRouter; distinguish 143 reply-gate fixtures from extractor-duplicate fixtures by file and name

**Target Platform**: Conversation `write_memory` after companion (or any agent) `remember_fact`

**Project Type**: Same-turn persist gate (identity + `ok`), not a classifier rewrite

**Performance Goals**: Filter is in-memory over this turn’s tool calls and extractor list

**Constraints**: Plugin code never imports `ze_core`. Principle VIII: one persist rule, no second extract door that ignores it. Hard non-LLM `speech_act` classifier is out of scope.

**Scale/Scope**: Engine memory node + small `ze_memory` identity helper + tests + docs. No plugin honesty rewrite (143). No inbound-mail race (no in-turn `remember_fact`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 148 + this plan | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Identity helper in `ze_memory`; persist filter in `ze_core` `write_memory`; plugins unchanged except they must not import `ze_core`. Messenger inbound is not this same-turn race | PASS |
| IV. Typed, Explicit Python | Identity key as a small dataclass or tuple helper in `ze_memory`; no Pydantic in domain | PASS |
| V. Test Discipline | Dual-write tests in ze-core (and identity unit tests in ze-memory); 143 model-lie tests stay in companion honesty files | PASS |
| VI. Explicit Persistence | No schema change | PASS |
| VII. One LLM Gateway | Extraction still uses injected `LLMClient`; no new provider | PASS |
| VIII. Pre-v1 Hard Cuts | Predicate-only skip keyed on `ToolCall.success` is replaced, not flagged beside a second rule. No dual extract persist path | PASS |

**Post-design re-check**: Contract pins `remember_fact` payload `ok`, identity `(predicate, value)` after 140-style normalize, single `write_memory` persist filter. Classifier and 144–147/149/`/memories` stay out. PASS.

## Project Structure

```text
specs/phases/148-extractor-dual-write/
├── plan.md
├── research.md
├── data-model.md
├── contracts/
│   └── extractor-same-turn-dedup.md
└── tasks.md

core/cognition/ze-memory/ze_memory/fact_identity.py          # identity key + remember ok parse
core/cognition/ze-memory/ze_memory/extractor.py              # no classifier rewrite; re-export if needed
core/cognition/ze-memory/tests/test_fact_identity.py
core/engine/ze-core/ze_core/orchestration/nodes/memory.py    # filter on ok + identity
core/engine/ze-core/tests/orchestration/nodes/test_memory.py # keep existing; do not assert 143 lies here
core/engine/ze-core/tests/orchestration/nodes/test_extractor_dual_write.py
plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py  # 143 only; no duplicate-row asserts
docs/memory.md
docs/cognitive-architecture.md
specs/core/ze-memory.md
specs/arch/memory-honesty-roadmap.md                         # 148 races done pointer only if docs pass
```

**Structure Decision:** Same-turn remember vs extract is an engine persist filter plus a core identity helper. Companion honesty stays reply-path (143). Do not put the skip inside plugins.

## Complexity Tracking

> None
