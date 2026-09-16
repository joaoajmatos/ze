# Implementation Plan: Specialist Memory Constitution

**Branch**: `149-specialist-memory-constitution` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/149-specialist-memory-constitution/spec.md`

## Summary

Calendar, messenger (mail), and news already call `BaseAgent._build_system_prompt`, so Phase 141’s constitution-then-job-then-biography order is already the shared assembler. This phase does not add a second builder. It rewrites those three agents’ domain instruction strings so they share companion’s 141 memory family (silent fact use, no unsolicited “I remember that you…” framing, no fake `remember_fact` / `forget_fact` success) while keeping ISO times, send rules, and news grounding. Catalogs stay without remember/forget tools (Phase 142). Unearned remember/forget **success claims** on the specialist turn path reuse companion `enforce_memory_confirmations` (import from `ze_personal`; add `ze-personal` to news). Do **not** lift claim dialect into `ze_agents`. Not a Phase 145 recitation product as a separate gate, not a Phase 144 write veto.

## Project Structure

```text
specs/phases/149-specialist-memory-constitution/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── prompt-order.md
│   ├── specialist-instructions.md
│   ├── remember-claim-honesty.md
│   └── specialist-constitution.md
└── tasks.md

plugins/ze-personal/ze_personal/agents/companion/honesty.py
plugins/ze-personal/ze_personal/agents/companion/agent.py
plugins/ze-calendar/ze_calendar/agents/calendar/agent.py
plugins/ze-messenger/ze_messenger/agents/messenger/agent.py
plugins/ze-news/ze_news/agents/agent.py
plugins/ze-calendar/tests/agents/calendar/test_calendar_agent.py
plugins/ze-messenger/tests/agents/messenger/test_messenger_agent.py
plugins/ze-news/tests/agents/test_news_agent.py
core/engine/ze-core/tests/orchestration/test_base_agent.py
docs/memory.md
specs/core/ze-agents.md
```

**Structure Decision**: Keep prompt assembly in `BaseAgent._build_system_prompt`. Keep the earned-confirmation function in companion honesty. Calendar/messenger already depend on `ze-personal`; news gains that dependency so all three import one door. Domain jobs stay in each plugin’s `_AGENT_INSTRUCTIONS`. Do not touch prospecting, goals, workflows, or reminders.

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 149 + this plan | PASS |
| II. Single-User | No `user_id` or tenancy | PASS |
| III. Layered Package Architecture | Plugins import `ze_sdk` / owning plugin / `ze_personal` honesty; never `ze_core`. Claim dialect stays out of `ze_agents` (144). No engine import from plugins | PASS |
| IV. Typed, Explicit Python | No new Pydantic models; existing dataclasses / `ToolCall` | PASS |
| V. Test Discipline | Prompt-order, catalog, instruction-family, and unearned-claim tests in calendar, messenger, and news packages (mocked LLM, no real DB) | PASS |
| VI. Explicit Persistence | No schema or migration | PASS |
| VII. One LLM Gateway | No new LLM; gate is deterministic | PASS |
| VIII. Pre-v1 Hard Cuts | One constitution family; one confirmation gate (moved, not copied). No specialist remember API beside companion’s tools. No wrap of a contradictory memory-chat dialect | PASS |

**Post-design re-check**: Biography remains after job. Recitation **reply** stripping stays Phase 145. Constraint veto stays Phase 144. PASS.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `MEMORY_CONSTITUTION` / `_build_system_prompt`; companion `enforce_memory_confirmations`; plugin agents in `ze-calendar`, `ze-messenger`, `ze-news`

**Storage**: None

**Testing**: `make test-calendar`, `make test-messenger`, `make test-news`, `make test-personal` (companion import path), `make test-agents` / `make test-sdk` after the gate module moves

**Constraints**: Do not add `remember_fact` / `forget_fact` to specialist `tools`. Do not implement 144 veto, 146–148, or 145 recitation stripping. Do not rewrite 140–142 contracts as a bundle.
