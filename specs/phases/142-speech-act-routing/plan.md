# Implementation Plan: Speech-Act Routing Across Stores

**Branch**: `142-speech-act-routing` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/142-speech-act-routing/spec.md`

## Summary

Add a conservative speech-act gate (same spirit as open-loop extraction) that classifies utterances into the spec’s R1–R14 table. Fact extraction drops commitments and timed remember-to-act. Companion (with Phase 140 tools) hands off timed/loop/goal/ingest acts via existing `delegate_to_agent` / domain agents rather than new specialist catalogs. No silent fact+reminder dual-write. Constraint veto (P5) is not implemented.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Phase 140 tools; `ze-memory` extractor; companion + `delegate_to_agent`; reminders agent (`set_reminder`); worldstate loop inflow; goal agent; ingestion. Optional reuse of `ze_worldstate.extraction` only from engine/inflow — do not make ze-memory depend on ze-worldstate.

**Storage**: No new tables. Writes go to existing reminder / loop / goal / fact / ingest stores.

**Testing**: Unit tests for classifier + extractor drop; companion routing tests with mocked delegate; eval fixtures extending `eval/scenarios/memory.yaml` (and reminder/goal if needed)

**Target Platform**: Backend turn admission + companion

**Project Type**: Routing policy over existing stores

**Performance Goals**: One cheap classification LLM call per turn (can combine with fact keep/drop JSON to avoid a second call — preferred)

**Constraints**: Do not add remember tools to news/prospecting/goals. Companion description today says it is “not for reminders” — update description + tools to allow **handoff**, not a cloned reminder implementation. Plugin still must not import `ze_core`.

**Scale/Scope**: Classifier + extractor alignment + companion instructions/tools list (`delegate_to_agent`) + eval table rows

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 142 + normative table | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Classifier in `ze-memory` (admission) or `ze-personal` companion; delegates to plugins via existing agent names | PASS |
| IV. Typed, Explicit Python | `SpeechAct` enum in `types.py` | PASS |
| V. Test Discipline | Table-driven tests per R-row | PASS |
| VI. Explicit Persistence | No new tables | PASS |
| VII. One LLM Gateway | Classification via `LLMClient` | PASS |
| VIII. Pre-v1 Hard Cuts | Extractor eating commitments is deleted behavior, not shimmed | PASS |

**Post-design re-check**: Combined JSON gate avoids dual LLM if research holds. PASS.

## Project Structure

```text
specs/phases/142-speech-act-routing/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── routing-table.md
└── tasks.md

core/cognition/ze-memory/ze_memory/extractor.py     # combined keep/drop + speech act
core/cognition/ze-memory/ze_memory/types.py         # SpeechAct enum (or extractor-local)
plugins/ze-personal/ze_personal/agents/companion/agent.py  # description + delegate_to_agent
plugins/ze-personal/ze_personal/agents/companion/tools.py  # remember/forget from 140; no set_reminder clone
eval/scenarios/memory.yaml
```

**Structure Decision:** Classify at extraction time (already post-turn and in-turn tools). In-turn: companion instructions + `delegate_to_agent` for R3–R8, R6, R7. Post-turn: extractor cannot create facts for those acts even if companion failed to hand off.

## Complexity Tracking

> None
