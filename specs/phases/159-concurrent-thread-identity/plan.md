# Implementation Plan: Concurrent Thread Identity

**Branch**: `159-concurrent-thread-identity` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/159-concurrent-thread-identity/spec.md`

## Summary

Finish Phase 99 for conductor/promote: per-thread trace, cancel, and timeout identity. Keep one live WebSocket (4000). Do not rebuild multiplexing.

## Technical Context

**Language/Version**: TypeScript (ze-web) + Python 3.12 (ze-api)

**Primary Dependencies**: `useTraceSocket` / `useTraceStore`, WS `command` handler, `Container._abort_tokens`, 157 timeout/promote copy, 113 `pending_configs`

**Storage**: None

**Testing**: vitest trace isolation; pytest cancel dual-pending; existing `test_ws` 4000

**Target Platform**: Chat + trace panel + WS commands

**Project Type**: Completion of 99 (M)

**Performance Goals**: No extra LLM

**Constraints**: Single-user; Principle VIII; 151–158 unchanged

**Scale/Scope**: Client trace store + command cancel targeting + timeout frame field + index honesty

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 159 | PASS |
| II. Single-User | One live client (4000) | PASS |
| III. Layered Package Architecture | Web + api shell; no plugin calendar imports | PASS |
| IV. Typed, Explicit Python | Existing dataclasses | PASS |
| V. Test Discipline | Fail-first dual-thread | PASS |
| VI. Explicit Persistence | No new tables | PASS |
| VII. One LLM Gateway | N/A | PASS |
| VIII. Pre-v1 Hard Cuts | No shim dual ConnectionManager | PASS |

**Post-design re-check**: Do not pass `None` pending_config into cancel as “any.” PASS.

## Project Structure

```text
apps/ze-web/src/features/trace-state/
apps/ze-api/ze_api/api/websocket/endpoint.py
apps/ze-api/ze_api/api/websocket/commands.py
apps/ze-api/ze_api/api/websocket/confirmation.py
```

## Complexity Tracking

> Guardrail: web+api — full pipeline.
