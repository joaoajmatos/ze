# Implementation Plan: Forget vs Cancel Across Stores

**Branch**: `146-forget-vs-cancel` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/146-forget-vs-cancel/spec.md`

## Summary

Colloquial “forget the dentist” still lands as biography `forget_fact`. Close R14 on the turn path: classify cancel/drop/abandon speech as reminder, loop, or goal (not `forget`); companion hands off to existing `cancel_reminder`, `close_loop`/`drop_loop`, and `abandon_goal`; never dual-write `forget_fact` for that same speech act. Forgotten-fact claims stay Phase 143-earned (`forget_fact` `ok` true). Domain confirmations are earned only from a successful domain tool this turn. Short-token multi-match asks or misses — do not batch-cancel every dentist reminder.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Companion `delegate_to_agent`; reminders `list_reminders` / `cancel_reminder`; goals `list_goals` / `abandon_goal`; worldstate `review.close_loop` / `drop_loop`; Phase 142 `SpeechAct` + extractor JSON; Phase 143 `enforce_memory_confirmations`

**Storage**: No new tables. Reminder delete, loop `closed`/`dropped`, goal `abandoned`, fact `contradicted` stay on their existing writers.

**Testing**: Extractor table tests (cancel speech ≠ `forget`); companion instruction + dual-write tests with mocked delegate; precise label-match unit tests; honesty gate tests for forgotten vs cancelled claims; eval YAML for “forget the dentist” vs aisle-seat forget. No OpenRouter, no real DB.

**Target Platform**: Companion turn + owning domain agents

**Project Type**: Routing honesty over existing stores

**Performance Goals**: No extra LLM call. Label match is in-process over the already-listed pending set.

**Constraints**: Plugin code imports `ze_sdk` / owning package, never `ze_core`. Principle VIII: no “also forget_fact just in case.” Do not start Phase 144 veto, 145 recitation, 147 ingest honesty, 148 extractor races, 149 specialist constitution bundle, or a `/memories` filesystem.

**Scale/Scope**: Extractor prompt + `SpeechAct` meaning of `forget`; companion R14 instructions; loop conversational tools wrapping existing review; nested delegate tool visibility for the honesty gate; conservative label match; eval + docs

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 146 + this plan | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Extractor in `ze-memory`; companion instructions in `ze-personal`; reminder cancel in `ze-calendar`; goal abandon in `ze-automation`; loop close/drop tools in `ze-worldstate`; plugins do not import `ze_core` | PASS |
| IV. Typed, Explicit Python | Match outcome dataclass (unique / miss / ambiguous); domain tool payloads stay dicts; no Pydantic in domain | PASS |
| V. Test Discipline | Gate + matcher + extractor + companion/reminder tests with mocks | PASS |
| VI. Explicit Persistence | No schema change | PASS |
| VII. One LLM Gateway | Routing uses existing extractor JSON + agentic tools; match is not an LLM call | PASS |
| VIII. Pre-v1 Hard Cuts | Delete the default “forget the dentist → `forget_fact`” path; no shim dual-write | PASS |

**Post-design re-check**: Contracts pin R14 primary store, nested delegate `tool_calls`, `ok` only for biography forget, and unique-label cancel. Dual doors rejected in research. PASS.

## Project Structure

```text
specs/phases/146-forget-vs-cancel/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── r14-cancel-routing.md
│   ├── nested-delegate-tools.md
│   ├── precise-cancel-match.md
│   └── earned-cancel-confirmation.md
└── tasks.md

core/cognition/ze-memory/ze_memory/extractor.py
core/cognition/ze-memory/ze_memory/types.py          # SpeechAct.FORGET meaning only (docs in extractor)
core/cognition/ze-memory/tests/test_speech_act_gate.py
core/contracts/ze-agents/ze_agents/delegate.py       # forward nested tool_calls
core/contracts/ze-agents/ze_agents/label_match.py    # unique / miss / ambiguous
core/cognition/ze-worldstate/ze_worldstate/agents/   # list / close_loop / drop_loop @tools + loops agent
plugins/ze-personal/ze_personal/agents/companion/agent.py
plugins/ze-personal/ze_personal/agents/companion/honesty.py
plugins/ze-personal/tests/agents/companion/test_speech_act_routing.py
plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py
plugins/ze-calendar/ze_calendar/agents/reminders/agent.py
plugins/ze-calendar/ze_calendar/agents/reminders/tools.py
core/automation/ze-automation/ze_automation/agents/goals/agent.py
eval/scenarios/memory.yaml
eval/scenarios/reminders.yaml
docs/memory.md
specs/core/ze-memory.md
specs/core/ze-agents.md
specs/arch/memory-honesty-roadmap.md                 # living pointer only
```

**Structure Decision:** Companion stays a handoff agent (`delegate_to_agent`). Domain writes stay on existing tools. Loops get a conversational agent that wraps `review.close_loop` / `drop_loop` so companion does not import `ze_core` or clone reminder tools. Shared label-match lives in `ze-agents` (no domain vocabulary). Forgotten-fact dialect stays companion-local (Phase 143).

## Complexity Tracking

> None
