# Implementation Plan: Action Record Ledger

**Branch**: `135-action-record-ledger` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

## Summary

Add a `ze-memory`-owned append-only `action_records` ledger. Hard-cut the contribution doctrine
so Action is licensed only for `ACTION_RECORD`; validate and append one immutable evidence record
per idempotency key. Workspace runs and one outbound messenger send are the reference producers.
Their source tables remain authoritative. Failure delivery is recoverable without replaying the
side effect. No public UI/API, generic arbitration, or `signal_sources()` rewire.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: `ze_agents.claims`, `ze_plugin.contribution`, `ze_collision` validated
submit wrapper, `ze_memory`, `ze_workspace`, `ze_messenger`, `ze_communication`  
**Storage**: new `ze-memory` `action_records` table; next free `zm` migration; no plugin-owned
table migration  
**Testing**: pytest + `AsyncMock`, no real DB/LLM; `make test-memory`, `make test-workspace`,
`make test-messenger`, `make test-plugin`, `make lint`  
**Target Platform**: backend only  
**Constraints**: append-only, unique idempotency key, typed `ZeError`, no Pydantic in domains,
no inline imports, pre-v1 hard cut, source records remain authoritative  
**Scale/Scope**: one shared claim-kind/contract change, one `ze-memory` store/migration, two
producer adapters, a durable handoff/retry integration where source transaction boundaries need it

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec, research, data model, contract, tasks, and quickstart exist | PASS |
| II. Single-User | Ledger has no tenancy field | PASS |
| III. Layered Package Architecture | Shared kind/contract lives in contracts; ledger lives in cognition; plugins retain source ownership and import via SDK | PASS |
| IV. Typed, Explicit Python | Dataclasses/enums/protocols; typed errors; opaque source identifiers | PASS |
| V. Test Discipline | Store, validation, idempotency, lifecycle, producer, and failure tests mock I/O | PASS |
| VI. Explicit Persistence | One `zm` migration owns one ledger table and constraints | PASS |
| VII. One LLM Gateway | No LLM path | PASS |
| VIII. Pre-v1 Hard Cuts | Empty ACTION license becomes ACTION_RECORD-only; no shim, dual-write, or dual-read | PASS |

**Post-design re-check:** ActionRecord's thin normalized record preserves domain ownership and
does not pre-commit to generic arbitration. PASS.

## Project Structure

```text
specs/phases/135-action-record-ledger/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/action-records.md
├── quickstart.md
├── tasks.md
├── checklists/requirements.md
└── .spec-context.json
```

```text
core/contracts/ze-agents/ze_agents/claims.py                 # ACTION_RECORD
core/contracts/ze-plugin/ze_plugin/contribution.py           # license, payload, validation
core/cognition/ze-memory/ze_memory/action_records/           # types, store, submit helper
core/cognition/ze-memory/ze_memory/migrations/versions/      # next zm migration
packages/ze-sdk/ze_sdk/contribution.py                       # contract re-export
core/ops/ze-workspace/ze_workspace/                          # workspace adapter/handoff
plugins/ze-messenger/ze_messenger/                           # outbound-message adapter/handoff
core/cognition/ze-memory/tests/
core/ops/ze-workspace/tests/
plugins/ze-messenger/tests/
```

**Structure Decision:** Keep normalized cross-domain evidence in `ze-memory`; retain source
execution details and mutations in their owner package. Use source-local adapters, not a generic
plugin event bus.

## Complexity Tracking

None.
