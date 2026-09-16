# Research: Eval `memory_proposals_count` Hard-Cut

**Feature**: `150-eval-guide-honesty`  
**Date**: 2026-09-16

## 1. Field is a shim

**Finding:** `EvalChatResponse.memory_proposals_count` defaults to 0. Eval route always assigns 0. MCP and `docs/eval.md` document it as legacy. `AgentResult.memory_proposals` is gone.

**Decision:** Delete the field from Pydantic, route construction, MCP docs, generated TS, tests, eval docs. No alias. No always-0 comment.

**Rejected:** Strip-filter in MCP while schema still has the field. Hand-edit `types.gen.ts` while Python still emits the field.

## 2. Codegen

**Decision:** After Python OpenAPI change, `bun run scripts/codegen.ts` in `packages/ze-client` (or the repo’s documented codegen target).

## 3. Guides

**Decision:** Sync `AGENTS.md` and `CLAUDE.md` phase tables through 143 Implemented and 144–150 Ready-to-implement or Pending matching `specs/README.md` at implement time. No Phase 151 directory.

## 4. Out of scope

144–149 product. Restoring `AgentResult.memory_proposals`.
