# Implementation Plan: Memory Admission and Conversational Remember/Forget

**Branch**: `140-memory-admission` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/phases/140-memory-admission/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Replace the every-turn Haiku fact extractor with a conservative keep/drop gate and closed predicate families, modeled on open-loop extraction. Add `remember_fact` / `forget_fact` on companion; successful remembers submit `PROMPT_SUPPLIED` + `reviewed=true` facts through `submit_perception_facts` (seam + NLI). Hard-cut `AgentResult.memory_proposals` off the persist path and the type. Ze may confirm memory only from tool success. Extraction may remain if it usually returns `[]`.

## Technical Context

**Language/Version**: Python 3.12 (asyncio-native)

**Primary Dependencies**: `ze-memory` (extractor, `Fact`, `submit_perception_facts`), `ze-personal` (companion), `ze-agents` (`@tool`, `AgentResult`), `ze-collision` / contribution seam, NLI via existing persist path

**Storage**: Existing `memory_facts` (no new table). Forget sets `contradicted=true` (and retrieval already filters contradicted). No migration unless Protocol needs a dedicated forget SQL — prefer one private store method, not a new column.

**Testing**: pytest mocks (no real DB/LLM). Eval YAML fixtures: remember / forget / ephemeral / constraint / commitment. Package targets: `make test-memory`, `make test-personal`, `make test-core` (write_memory), `make test-agents` (AgentResult).

**Target Platform**: Backend (`ze-memory`, `ze-personal`, `ze-core` write_memory)

**Project Type**: Hard-cut inside existing packages

**Performance Goals**: Extraction still one cheap synthesis-model call per turn; gate should return `[]` on empty turns without extra LLM if the prompt is empty/trivial — plan allows a cheap pre-check then one LLM.

**Constraints**: Principle VIII — no dual door with `memory_proposals`. User-supplied does not skip the seam. Plugin tools import `ze_sdk` / `ze_memory`, never `ze_core`.

**Scale/Scope**: Single-user; companion-only tools this phase; extractor prompt rewrite; AgentResult field removal

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| I. Spec-First | Spec 140 exists | PASS |
| II. Single-User | No `user_id` | PASS |
| III. Layered Package Architecture | Tools in `ze-personal`; extraction + submit in `ze-memory`; engine `write_memory` only drops proposals persist | PASS |
| IV. Typed, Explicit Python | Dataclass facts; typed `ZeError` on tool failure; `@tool` | PASS |
| V. Test Discipline | Mock pool/LLM; eval fixtures | PASS |
| VI. Explicit Persistence | No new table; optional forget method on existing rows | PASS |
| VII. One LLM Gateway | Extractor still `LLMClient` / OpenRouter synthesis model | PASS |
| VIII. Pre-v1 Hard Cuts | Remove `memory_proposals` persist + field; no shim | PASS |

No violations.

**Post-design re-check**: Single explicit door is the tools; extraction is synthesized-only. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/phases/140-memory-admission/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── remember-forget-tools.md
│   └── fact-admission-gate.md
└── tasks.md
```

### Source Code (repository root)

```text
core/cognition/ze-memory/ze_memory/
├── extractor.py              # keep/drop gate, closed families, commitment drop
├── contribution.py           # unchanged submit_perception_facts
├── store.py / retriever.py   # forget: mark contradicted (private persist)

plugins/ze-personal/ze_personal/agents/companion/
├── agent.py                  # tools = [remember_fact, forget_fact]
└── tools.py                  # NEW @tool remember_fact / forget_fact

plugins/ze-personal/ze_personal/plugin.py  # agent_module_paths: tools then agent

core/engine/ze-core/ze_core/orchestration/nodes/memory.py  # stop persisting memory_proposals
core/contracts/ze-agents/ze_agents/types.py               # drop memory_proposals field

eval/scenarios/memory.yaml    # new fixtures
core/cognition/ze-memory/tests/
plugins/ze-personal/tests/agents/companion/
core/engine/ze-core/tests/orchestration/nodes/test_memory.py
```

**Structure Decision**: Admission policy lives in `ze_memory/extractor.py` (already the post-turn writer). Tools live beside companion so the plugin owns the speech-act UX; they call `submit_perception_facts` like `write_memory` does. Engine only loses the unused proposals merge.

## Complexity Tracking

> None
