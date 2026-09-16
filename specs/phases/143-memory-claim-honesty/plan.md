# Implementation Plan: Earned Memory Confirmations and Precise Forget

**Branch**: `143-memory-claim-honesty` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/143-memory-claim-honesty/spec.md`

## Summary

Companion still confirms remembered and forgotten from model prose. Close that on the turn path: after `agentic_loop`, confirmations are allowed only when `remember_fact` or `forget_fact` returned `ok` true. Buffer WebSocket tokens so the live stream cannot skip the gate. Tighten `_retract_facts_matching` so forget prefers a miss over substring or top-5 cosine over-retract. No prompt-only fix, no shim of the old matcher.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Existing companion tools; `BaseAgent.agentic_loop`; `PostgresMemoryStore._retract_facts_matching`; local embedder for the unique-neighbor forget fallback

**Storage**: No new tables. Forget still sets `memory_facts.contradicted = true` on matched ids.

**Testing**: Unit tests for the confirmation gate (no OpenRouter); forget matcher table tests with mocked pool/embedder; companion `run`/`stream`/`token_sink` tests; eval YAML criteria hard-cut

**Target Platform**: Companion turn + memory store

**Project Type**: Honesty gate + matcher hard-cut

**Performance Goals**: Gate is CPU-only on the final reply. Forget still scans at most 200 live facts.

**Constraints**: Plugin code imports `ze_sdk` / `ze_agents` / `ze_personal`, never `ze_core`. Principle VIII: delete the `stream` bypass and the substring/top-5 matcher; do not flag them. Do not start P5 veto.

**Scale/Scope**: One plugin honesty module, companion `run`/`stream`, retriever matcher, tests, eval criteria, docs/memory.md touch

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 143 + this plan | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Confirmation dialect in `ze-personal`; matcher in `ze-memory`; plugins do not import `ze_core` | PASS |
| IV. Typed, Explicit Python | Dataclass for gate input/result in companion `types` or module-local; no Pydantic in domain | PASS |
| V. Test Discipline | Gate + matcher + companion path tests with mocks | PASS |
| VI. Explicit Persistence | No schema change | PASS |
| VII. One LLM Gateway | Gate is not an LLM call; forget embedder is the existing local model | PASS |
| VIII. Pre-v1 Hard Cuts | Old substring/top-5 matcher and tool-free `CompanionAgent.stream` are removed, not wrapped | PASS |

**Post-design re-check**: Contracts pin `ok` payload and matcher ladder. Dual doors rejected in research. PASS.

## Project Structure

```text
specs/phases/143-memory-claim-honesty/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── earned-confirmation-gate.md
│   └── forget-match.md
└── tasks.md

plugins/ze-personal/ze_personal/agents/companion/honesty.py   # new: gate + sink buffer helper
plugins/ze-personal/ze_personal/agents/companion/agent.py     # run/stream/token_sink
plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py
plugins/ze-personal/tests/agents/companion/test_companion_agent.py
core/cognition/ze-memory/ze_memory/retriever.py               # _retract_facts_matching
core/cognition/ze-memory/tests/test_forget_retract.py
eval/scenarios/memory.yaml
docs/memory.md
specs/arch/memory-honesty-roadmap.md                          # living follow-ons (not extra speckit dirs)
```

**Structure Decision:** Companion owns user-visible confirmation language. Memory store owns match precision. Engine `agentic_loop` stays generic.

## Complexity Tracking

> None
