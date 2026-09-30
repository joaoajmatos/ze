# Implementation Plan: System One Client

**Branch**: `162-system-one-client` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/162-system-one-client/spec.md`. User pin: OpenRouter Jev `typesafe/jev-1.13`.

## Summary

162 adds a constructor-injected `SystemOneClient` so later phases can ask closed questions (noul / choice / score) and read probabilities without parsing LLM JSON. The engine posts to OpenRouter’s native System One path with the existing `OPENROUTER_API_KEY` and pinned model `typesafe/jev-1.13`; it does not use chat completions, a TypeSafe-native key, or `typesafe-sdk`. Default config is off and fail-open, so turns, admission, and routing stay as they are. `MessageTrace.judgments` is the explainability hook; production traces stay empty until 163/164.

## Technical Context

**Language/Version**: Python 3.11+ (existing packages); TypeScript for ze-web trace panel

**Primary Dependencies**: Existing `openrouter==0.9.1` for chat; `httpx==0.28.1` on ze-core for `POST /systemone` until the SDK grows `system_one.create`; no `typesafe-sdk`

**Storage**: No new tables. `messages.trace` JSONB gains `judgments` (default `[]`)

**Testing**: pytest with mocked HTTP; vitest for the trace section. Default CI never calls OpenRouter. Optional `@pytest.mark.slow` live call only if added later

**Target Platform**: ze-api process + ze-web trace panel

**Project Type**: monorepo feature (contracts + engine + API schema + web)

**Performance Goals**: Client timeout default 2000 ms; skip on timeout. No extra LLM hop in 162

**Constraints**: Principle VII — generative LLM still `LLMClient` + OpenRouter chat. Judgments are not LLMs; they use OpenRouter System One on the **same** key. Fail-open. FR-009: no admission/routing/skill/retrieval/push/dream change. Plugins import Protocol from `ze_sdk` only

**Scale/Scope**: Single-user. Protocol + one HTTP impl + DI + trace schema + empty-safe UI. No production questions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source: `.specify/memory/constitution.md`.*

| Principle | Assessment |
|---|---|
| I. Spec-First Development | PASS — phase spec + governing arch note before implement |
| II. Single-User Model | PASS — one OpenRouter key, no tenant scoping |
| III. Layered Package Architecture | PASS — Protocol in `ze_agents`, HTTP in `ze_core`, plugins via `ze_sdk` |
| IV. Typed, Explicit Python | PASS — dataclasses in `types.py` / `system_one.py`; Pydantic only in `ze_api/api/schemas.py`; typed skip reasons; `get_logger` |
| V. Test Discipline | PASS — mock HTTP; no live vendor in default `make test`; no real DB |
| VI. Explicit Persistence | PASS — no migration; JSONB field additive with default |
| VII. One LLM Gateway, Local Embeddings | PASS — chat stays on `LLMClient` / OpenRouter. Jev is not an LLM and is **not** called via `complete()`. Billing and auth stay `OPENROUTER_API_KEY`. Local E5/NLI untouched. Hard-cut: no second TypeSafe key |
| VIII. Pre-v1 Hard Cuts | PASS — rewrite FR-010 and arch secret/model pins; no dual `TYPESAFE_API_KEY` or chat-tunnel shim |

**Post-design re-check**: HTTP contract is System One (`/systemone`), not chat and not Decisions alpha. Trace field is additive with default `[]` (old rows still parse). Disabled client means zero network. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/phases/162-system-one-client/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── system-one-client.md
│   ├── openrouter-systemone-http.md
│   └── trace-judgments.md
└── spec.md
```

### Source Code (repository root)

```text
core/contracts/ze-agents/ze_agents/system_one.py
core/contracts/ze-agents/ze_agents/errors.py          # skip is not an exception; optional SystemOneError unused on the hot path
packages/ze-sdk/ze_sdk/__init__.py
core/engine/ze-core/ze_core/openrouter/system_one.py  # OpenRouterSystemOneClient + DisabledSystemOneClient
core/engine/ze-core/ze_core/bootstrap.py
core/engine/ze-core/ze_core/orchestration/state.py
core/engine/ze-core/ze_core/orchestration/nodes/trace.py
core/engine/ze-core/ze_core/conversation/turn.py
core/engine/ze-core/ze_core/conversation/messages/types.py
core/engine/ze-core/tests/openrouter/test_system_one.py
core/engine/ze-core/tests/orchestration/nodes/test_trace_judgments.py
apps/ze-api/ze_api/container.py
apps/ze-api/ze_api/api/schemas.py
apps/ze-api/ze_api/api/messages.py
apps/ze-api/config/config.yaml
apps/ze-api/tests/api/test_judgments_trace_schema.py
apps/ze-web/src/widgets/trace-panel/ui/JudgmentsSection.tsx
apps/ze-web/src/widgets/trace-panel/ui/TraceEntry.tsx
apps/ze-web/src/features/trace-state/lib/toTraceFrame.ts
specs/arch/system-one-models.md
specs/core/ze-agents.md
specs/core/ze-core.md
```

**Structure Decision**: Copy NLI 080: Protocol in ze-agents, OpenRouter-backed impl beside `OpenRouterClient`, compose in `build_engine_stack` / ZeContainer, explainability on existing `MessageTrace`.

## Complexity Tracking

> No constitution violations.
