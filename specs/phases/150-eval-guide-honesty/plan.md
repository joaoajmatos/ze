# Implementation Plan: Eval `memory_proposals_count` Hard-Cut and Guide Phase-Index Honesty

**Branch**: `150-eval-guide-honesty` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/150-eval-guide-honesty/spec.md`

## Summary

Eval still publishes `EvalChatResponse.memory_proposals_count`, always `0`, after `AgentResult.memory_proposals` was removed. Delete that field from the Pydantic schema, `/eval/chat` handler, MCP tool docs, generated `@ze/client` types, `docs/eval.md`, and tests. Remember and forget are judged only from `tool_calls` (`remember_fact` / `forget_fact`). In the same phase, sync `AGENTS.md` and `CLAUDE.md` phase indexes through 143 Implemented (or the file’s equivalent Done token, copied from `specs/README.md` at implement) and list 144–150 as Pending. Roadmap 151 is bundled here; do not create a 151 directory and do not implement 144–149 product.

## Technical Context

**Language/Version**: Python 3.12; TypeScript generated client

**Primary Dependencies**: FastAPI/`EvalChatResponse` in `ze_api.api.schemas`; `bun run scripts/codegen.ts` (`@hey-api/openapi-ts`); MCP server in `ze_eval.server`

**Storage**: None. No migrations.

**Testing**: pytest in `apps/ze-api/tests` (schema + OpenAPI omit the field) and `core/ops/ze-eval/tests` if MCP docs are asserted; no real graph, no OpenRouter

**Target Platform**: Eval HTTP + MCP judge surface; agent-facing markdown indexes

**Project Type**: Pre-v1 hard-cut of a deleted eval contract field plus documentation honesty

**Performance Goals**: N/A

**Constraints**: Principle VIII — no alias, no always-0 leftover, no strip-filter if the schema still emits the field. Plugin code unchanged. Do not restore `AgentResult.memory_proposals`. Do not implement 144–149.

**Scale/Scope**: Schema, one route, MCP docstrings, codegen, two guides, eval docs, a small test delta

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 150 + this plan; bundles roadmap 151 in this directory | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Cut lives in `ze-api` schemas/routes and `ze-eval` MCP docs; no plugin `ze_core` import | PASS |
| IV. Typed, Explicit Python | Field removed from existing Pydantic `EvalChatResponse` (API schemas only) | PASS |
| V. Test Discipline | Assert the field is absent from the model and OpenAPI; rewrite/delete always-0 assertions | PASS |
| VI. Explicit Persistence | No tables | PASS |
| VII. One LLM Gateway | No new LLM path | PASS |
| VIII. Pre-v1 Hard Cuts | Delete the field; no deprecated alias and no “always 0” comment as a shim | PASS |

**Post-design re-check**: Contract document is the remaining `EvalChatResponse` plus an explicit Removed section. Dual doors (hand-edit client while Python still has the field; MCP strip-filter) rejected in research. PASS.

## Project Structure

```text
specs/phases/150-eval-guide-honesty/
├── plan.md
├── research.md
├── data-model.md
├── contracts/
│   └── eval-chat-response.md
└── tasks.md

apps/ze-api/ze_api/api/schemas.py                         # delete EvalChatResponse.memory_proposals_count
apps/ze-api/ze_api/api/routes/eval.py                     # stop assigning the field
apps/ze-api/tests/api/test_schemas.py                     # assert field absent
apps/ze-api/tests/api/test_openapi_export.py              # OpenAPI EvalChatResponse omits field
core/ops/ze-eval/ze_eval/server.py                        # MCP docstrings: no field
core/ops/ze-eval/tests/                                   # if docs/payload helpers mention it
packages/ze-client/src/generated/types.gen.ts             # REGEN via bun run scripts/codegen.ts
docs/eval.md                                              # drop table row; judge via tool_calls
AGENTS.md                                                 # phase index 140–150
CLAUDE.md                                                 # phase index 140–150
specs/arch/memory-honesty-roadmap.md                      # already points here; no 151 dir
```

**Structure Decision:** The eval HTTP schema is the contract. Guides are the same honesty class (roadmap 151) in this directory only.

## Complexity Tracking

> None
