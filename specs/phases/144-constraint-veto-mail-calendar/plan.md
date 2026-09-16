# Implementation Plan: Constraint Veto on Gated Writes

**Branch**: `144-constraint-veto-mail-calendar` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/144-constraint-veto-mail-calendar/spec.md`

## Summary

Reviewed standing constraints must actually stop (or confirm) writes plugins mark as `constraint_gate`. The check is one harness hook on `call_tool`, not a core list of mail/calendar names. First adopters: `send_email`, calendar create/update/delete, reminder set/cancel; prospecting send uses `send_email`. User-visible “I won’t … because of your constraint” is earned only when the hook set `veto` true. No new remember API.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `ToolSpec` / `@tool`; `HarnessHook.on_tool_start`; memory store reviewed facts; existing confirmation interrupt; companion honesty module

**Storage**: No new tables. Read `memory_facts` reviewed + `constraint` family.

**Testing**: Hook unit tests with a marked dummy tool; adopter tests for mail/calendar/reminders; matching table tests; honesty tests for unearned veto claims + token_sink; no real Google/LLM

**Target Platform**: Tool dispatch + first-adopter plugins

**Project Type**: Shared write gate + plugin marks

**Performance Goals**: Load reviewed constraints once per turn (cache on ctx) not per tool arg parse

**Constraints**: Plugins import `ze_sdk` / owning plugin, never `ze_core`. `constraint_gate` default false. Principle VIII: no ungated twin. Dialects stay out of `ze-agents`.

**Scale/Scope**: ze-agents ToolSpec + hook in ze-memory (store access) registered from ze-api bootstrap; marks on messenger/calendar/reminders tools; honesty helper; tests; docs/memory.md

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 144 + this plan | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Gate flag on tools (contracts); hook can live in ze-memory; plugins mark tools; channel/kind are strings not a core mail enum; plugins never import `ze_core` | PASS |
| IV. Typed, Explicit Python | Dataclass `ConstraintWriteView`; no Pydantic in domain | PASS |
| V. Test Discipline | Dummy gated tool + adopter + honesty tests, mocks | PASS |
| VI. Explicit Persistence | No schema change | PASS |
| VII. One LLM Gateway | Matcher is not an LLM call | PASS |
| VIII. Pre-v1 Hard Cuts | No wrap of an ungated send; no flagged old path | PASS |

**Post-design re-check**: Contracts pin `constraint_gate` and earned `veto`. Dummy-tool test forbids a name list. PASS.

## Project Structure

```text
specs/phases/144-constraint-veto-mail-calendar/
├── plan.md
├── research.md
├── data-model.md
├── contracts/
│   ├── constraint-gate.md
│   └── earned-veto-claim.md
└── tasks.md

core/contracts/ze-agents/ze_agents/tool.py          # constraint_gate on ToolSpec/@tool
core/cognition/ze-memory/ze_memory/constraint_veto.py  # hook + matcher
apps/ze-api/ze_api/  or ze-core bootstrap           # register_hook (composition root)
plugins/ze-messenger/.../tools.py                   # send_email, draft_email
plugins/ze-calendar/.../calendar/tools.py
plugins/ze-calendar/.../reminders/tools.py
plugins/ze-personal/.../companion/honesty.py        # earned veto claims
plugins/ze-personal/.../companion/agent.py          # drop “veto is later phase”
docs/memory.md
```

**Structure Decision:** Opt-in lives on the tool. Evaluation lives in one hook that can read memory. Claim honesty stays in the personal honesty module (and specialist `run` if those agents emit the line).

## Complexity Tracking

> None
