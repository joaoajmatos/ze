# Implementation Plan: Perception Facts onto the Contribution Seam

**Branch**: `133-perception-facts-seam` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/phases/133-perception-facts-seam/spec.md`

## Summary

Perception facts still call ungated `propose_facts`. This phase wraps each listed writer in the same envelope `ingest_signal` already uses: domain `Fact` + `Contribution` (`PERCEPTION` / `FACT` / honest `Provenance`) + `submit_and_detect_collisions(write=callback)`. Persist stays `propose_facts` / `_write_fact_with_contradiction_check` as the callback; call sites stop treating `propose_facts` as the front door. Provenance is stamped per fact after merge (explicit predicates → `PROMPT_SUPPLIED`, else `SYNTHESIZED`). Ingestion and goal ids go on `source_refs` and on `EvidenceRef` kinds that do not fail dangling checks. Goal-learning promotion is synthesized perception with the goal as evidence — not ACTION, not a new kind. No schema hard-cut (Phase 134). No PriorityView / surfacing / arbitration changes.

## Technical Context

**Language/Version**: Python 3.12 (monorepo default)

**Primary Dependencies**: `ze_plugin.contribution` (`Contribution`, `EvidenceRef`, `SourceFunction`, `TargetFace`), `ze_collision.detect.submit_and_detect_collisions`, `ze_agents.claims` (`ClaimKind`, `Provenance`, `Confidence`), existing `PostgresMemoryStore.propose_facts`

**Storage**: Existing `memory_facts` only. No Alembic migration this phase. `Fact.provenance` string dialect (`"raw"` / `"synthesized"`) unchanged on insert.

**Testing**: pytest, `asyncio_mode = "auto"`; `AsyncMock` stores; no real DB/LLM. Package targets: `make test-memory`, `make test-core`, `make test-ingestion`, `make test-onboarding`, `make test-automation` (or `test-personal` if onboarding is folded), messenger plugin tests, `make lint`

**Target Platform**: Backend (`ze-api` composition); no new REST or WebSocket frames

**Project Type**: Call-site migration across core packages + one plugin

**Performance Goals**: Same posture as `ingest_signal` — synchronous validate-then-write; collision detect remains fail-open fire-and-forget (Phase 126)

**Constraints**: Do not map `Provenance.SYNTHESIZED` onto `Fact.provenance == "synthesized"` (that insert path currently stores `claim_kind=INFERENCE`). Do not change `surface_loops`, resume recap, `rank_subset`, push budget, or arbitration. Do not delete `MemoryStore.propose_facts`

**Scale/Scope**: Six call sites + one helper + tests; no new tables

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 133 exists with FRs, stories, no `[NEEDS CLARIFICATION]` | PASS |
| II. Single-User | No `user_id` or tenancy | PASS |
| III. Layered Package Architecture | Helper lives in `ze_memory` (target of facts). Plugins (`ze-messenger`) and `ze-automation` / `ze-onboarding` / `ze-ingestion` call it via `ze_sdk` or existing `ze_memory` imports. Engine `write_memory` already depends on `ze_memory` through the store. No plugin imports `ze_core`. No new core enum values except extending `EvidenceRef.kind` with doctrine-adjacent citation kinds (`ingestion`, `goal`) — not plugin-domain channel names | PASS |
| IV. Typed, Explicit Python | Dataclasses / existing `Fact`; typed `ZeError` already used by the seam | PASS |
| V. Test Discipline | Unit tests mock pool/LLM; dedicated seam-rejection tests | PASS |
| VI. Explicit Persistence | No migration this phase | PASS |
| VII. One LLM Gateway | No new LLM path | PASS |
| VIII. Pre-v1 Hard Cuts | Call sites **replace** ungated `propose_facts` this phase (not wrap-then-replace across phases). `propose_facts` remains as the in-phase callback. Schema/Protocol deletion is Phase 134, not a lingering dual door | PASS |

No violations. Complexity Tracking omitted.

*Post-design re-check:* EvidenceRef kind extension + skip-dangling-for-unwired-citation-kinds is a small contract change in `ze-plugin`, justified so FACT citations do not require existence checkers for ingestion/goal rows. Still PASS III/VIII.

## Project Structure

### Documentation (this feature)

```text
specs/phases/133-perception-facts-seam/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/perception-facts-seam.md
└── tasks.md
```

### Source Code (repository root)

```text
core/contracts/ze-plugin/ze_plugin/contribution.py   # EvidenceRef.kind += ingestion, goal
core/cognition/ze-memory/ze_memory/contribution.py   # fact_to_contribution + submit helper
core/cognition/ze-memory/ze_memory/retriever.py      # optional thin store method; persist callback
core/engine/ze-core/ze_core/orchestration/nodes/memory.py
core/ops/ze-ingestion/ze_ingestion/sink.py
core/ops/ze-onboarding/ze_onboarding/persistence.py
core/automation/ze-automation/ze_automation/goals/executor.py
plugins/ze-messenger/ze_messenger/inbound/processor.py
packages/ze-sdk/ze_sdk/memory.py                     # re-export helper if plugins need it
# tests beside each package
```

**Structure Decision**: One `ze_memory` submit helper (mirror `signal_to_contribution` + `ingest_signal`); call sites switch to it; `propose_facts` stays the persist callback and Protocol method.

## Complexity Tracking

None.
