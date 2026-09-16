# Implementation Plan: Memory Read Contract and Prompt Constitution

**Branch**: `141-memory-prompt-constitution` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/141-memory-prompt-constitution/spec.md`

## Summary

Pin reviewed profile facts always-on in companion retrieval; keep similarity retrieval for the rest under the existing token budget. Rewrite `_format_memory` to show confidence, recency, and doctrine provenance. Reorder `_build_system_prompt` so shared constitution and the agent job precede biography (`build_identity_block` memory dump). Rewrite companion instructions for silent fact use. Do not add fact inline-mentions; leave `TurnSurfacing` for open items. Do not rewrite specialist agents. Constraint veto stays deferred.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `ze-agents` (`BaseAgent._build_system_prompt`, `_format_memory`), `ze-memory` (`CompanionPolicy`, `Fact` projection), `ze-personal` (`build_identity_block`, companion instructions), `ze-priority` (`TurnSurfacing` — read-only)

**Storage**: No schema change unless `Fact` projection is missing `created_at` (column already on `memory_facts`) — add field on the dataclass + `_fact_from_row` only.

**Testing**: `make test-agents`, `make test-memory`, `make test-personal`, `make test-core` (prompt order tests)

**Target Platform**: Backend prompt assembly

**Project Type**: Prompt/retrieval contract inside existing packages

**Performance Goals**: One extra reviewed-facts query (small, indexed boolean) plus existing similarity fetch; no new LLM on the read path

**Constraints**: Do not extend `TurnSurfacing` to facts. Do not disable mail/calendar tools. Prefer Phase 140 first so constitution can mention remember tools if present — constitution must not require tools that are absent.

**Scale/Scope**: Shared formatter + companion copy; identity template split; CompanionPolicy union

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 141 exists | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Shared prompt in `ze-agents`; identity in `ze-personal`; retrieval in `ze-memory`; no `ze_core` import from plugins | PASS |
| IV. Typed, Explicit Python | Provenance enum in formatter, not `"raw"` strings | PASS |
| V. Test Discipline | Unit tests on prompt order and formatter | PASS |
| VI. Explicit Persistence | Optional dataclass field only; no new table | PASS |
| VII. One LLM Gateway | No new LLM | PASS |
| VIII. Pre-v1 Hard Cuts | Replace old synthesized-vs-raw formatter; no dual dialect | PASS |

**Post-design re-check**: Biography stays in identity; constitution is a separate prefix. PASS.

## Project Structure

```text
specs/phases/141-memory-prompt-constitution/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── prompt-assembly.md
└── tasks.md

core/contracts/ze-agents/ze_agents/base_agent.py     # order + _format_memory
core/cognition/ze-memory/ze_memory/policies.py       # always-on reviewed facts
core/cognition/ze-memory/ze_memory/types.py          # Fact.created_at if missing
core/cognition/ze-memory/ze_memory/projection.py
plugins/ze-personal/ze_personal/persona/identity.py  # biography-only template
plugins/ze-personal/ze_personal/agents/companion/agent.py  # memory-use rules
core/arbitration/ze-priority/ze_priority/turn.py     # no fact mentions (assert in tests)
```

**Structure Decision**: Constitution lives in `BaseAgent` (all agents inherit order). Companion-specific silent-use rules live in companion `_AGENT_INSTRUCTIONS`. Identity builder becomes biography+persona traits, not the place for job instructions.

## Complexity Tracking

> None
