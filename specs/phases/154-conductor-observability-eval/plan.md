# Implementation Plan: Conductor Observability and Eval

**Branch**: `154-conductor-observability-eval` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/154-conductor-observability-eval/spec.md`

## Summary

Serialize 153’s conductor ledger onto REST/`trace_update`, render it in the trace panel, emit pinned progress keys during calendar then mail delegates, and add four eval scenarios that prove sequential companion routing, independent parallel not via companion, 146 speech-act honesty, and mid-sequence confirmation resume.

## Technical Context

**Language/Version**: Python 3.12; TypeScript ze-web + generated `@ze/client`

**Primary Dependencies**: `MessageTrace`, OpenAPI schemas, `TraceEntry`/`TraceContent`, companion locales, `eval/scenarios`

**Storage**: No new tables; JSON on existing message `trace`

**Testing**: pytest schema/trace; vitest trace panel; eval YAML present (full eval run optional in CI as today)

**Target Platform**: Trace side panel + typing progress + eval CLI

**Project Type**: Observability + eval honesty (S/M)

**Performance Goals**: No extra LLM

**Constraints**: Regenerate client types. Do not restore `plan_sequential`. Plugin locales not hardcoded in ze-core.

**Scale/Scope**: Trace types, one panel section, companion locale, four YAML scenarios, codegen

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 154 | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Progress keys in companion plugin locales; panel in ze-web; eval in eval/ | PASS |
| IV. Typed, Explicit Python | Trace dataclass + API schema | PASS |
| V. Test Discipline | Panel + schema + YAML ids | PASS |
| VI. Explicit Persistence | Existing trace JSONB | PASS |
| VII. One LLM Gateway | Eval may call models when run; no new gateway | PASS |
| VIII. Pre-v1 Hard Cuts | Additive trace fields; no dual plan_sequential | PASS |

**Post-design re-check**: Hand-edit `ws.ts` without OpenAPI rejected. PASS.

## Project Structure

```text
specs/phases/154-conductor-observability-eval/

core/engine/ze-core/ze_core/conversation/messages/types.py
apps/ze-api/ze_api/api/schemas.py                          # trace response + WS
packages/ze-client/                                        # codegen
apps/ze-web/src/widgets/trace-panel/
plugins/ze-personal/ze_personal/locales/en.yaml            # or companion locales
eval/scenarios/routing.yaml and/or conductor.yaml
```

**Structure Decision:** 153 owns ledger storage; 154 owns serialization, UI, progress copy, eval ids.

## Complexity Tracking

> None
