# Implementation Plan: E5 Routing Confidence

**Branch**: `160-e5-routing-confidence` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/160-e5-routing-confidence/spec.md`

## Summary

Finish Phase 97: keep E5, retune routing floor and gap so clear single-agent turns skip Haiku decompose, and hard-cut MiniLM from living docs. Do not change 153/155 rewrite. Do not swap the model.

## Technical Context

**Language/Version**: Python 3.12 (`ze-agents` defaults, `ze-core` router)

**Primary Dependencies**: `E5Embedder`, `EmbeddingRouter._score_and_route`, `RouterConfig`, YAML `routing` overlay in `ze_core.container`

**Storage**: None (97 already nulled MiniLM vectors)

**Testing**: `test_router.py` fixtures at E5-like scores; 153/155 tests unchanged; optional `@pytest.mark.slow` live E5

**Target Platform**: Routing hot path

**Project Type**: Completion of 97 (S/M)

**Performance Goals**: Fewer Haiku decompose calls on single-agent turns; no extra model load

**Constraints**: Principle VII (local embeddings) + VIII (no MiniLM+E5 dual); 153/155 frozen

**Scale/Scope**: Two floats + docs + tests

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 160 | PASS |
| II. Single-User | Unchanged | PASS |
| III. Layered Package Architecture | Defaults in `ze-agents`; router in `ze-core`; no plugin import of `ze_core` | PASS |
| IV. Typed, Explicit Python | Existing dataclasses | PASS |
| V. Test Discipline | Fail-first fixtures; slow real E5 marked | PASS |
| VI. Explicit Persistence | No schema | PASS |
| VII. One LLM Gateway, Local Embeddings | Amend the MiniLM name to E5 in the same phase as the defaults | PASS |
| VIII. Pre-v1 Hard Cuts | Replace MiniLM docs; no shim “MiniLM or E5” | PASS |

**Post-design re-check**: YAML overlay is not a compatibility shim for MiniLM defaults — defaults themselves change. PASS.

## Project Structure

```text
core/contracts/ze-agents/ze_agents/defaults.py
core/engine/ze-core/ze_core/routing/router.py          # predicate unchanged
core/engine/ze-core/tests/routing/test_router.py
apps/ze-api/config/config.yaml
.specify/memory/constitution.md
specs/arch/local-embeddings.md
AGENTS.md  CLAUDE.md  docs/architecture.md  specs/core/ze-core.md
```

**Structure Decision**: Change the named defaults; container already reads YAML over `RouterConfig()`.

## Complexity Tracking

> Guardrail: docs + defaults + tests — full pipeline. No constitution violation.
