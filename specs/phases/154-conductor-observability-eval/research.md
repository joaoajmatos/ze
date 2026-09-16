# Research: Conductor Observability and Eval

**Feature**: `154-conductor-observability-eval`  
**Date**: 2026-09-16

## 1. Additive trace fields

**Decision:** Extend `MessageTrace` / OpenAPI / `WsTraceUpdateFrame` with conductor plan/hint, ledger, confirmation ids. Panel section reads those fields. Old traces omit the section.

**Rejected:** A parallel `conductor_trace` REST resource.

## 2. Progress keys in companion locales

**Decision:** Pin `conductor.checking_calendar` and `conductor.drafting_mail` in companion/personal locale YAML. Reporter uses those keys when `run_delegate` starts those agents. Calendar-primary reads keep calendar plugin keys.

**Rejected:** Hardcoded strings in `ze_core`. Reusing only calendar plugin keys (user would not see mail next).

## 3. Four eval ids are the contract

**Decision:** Exact scenario ids from the spec. Sequential fixture must assert companion primary and event id in later `prior_outputs` or `inputs`. Independent parallel must fail if companion is primary.

**Rejected:** One vague “conductor” eval. Using `plan_sequential` to make sequential eval pass.

## 4. Codegen

**Decision:** After schema change, `bun run scripts/codegen.ts` (or documented script). Tests fail if TS lacks fields.

## 5. Out of scope stays out

**Decision:** No promote, no parallel per-subtask gate, no Magentic stall product. Ask/stall on the ledger is display-only of 153 statuses.
