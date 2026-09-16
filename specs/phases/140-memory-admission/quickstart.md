# Quickstart: Memory Admission (Phase 140)

## Prerequisites

- Spec + this plan; tests mock LLM/DB.
- Phases 133–134 already on the branch (seam + doctrine provenance).

## Validate

```bash
make test-memory
make test-personal
make test-core
make test-agents
make lint
```

## Scenarios (see contracts)

1. Empty/ephemeral/commitment prompts → extractor `[]`.
2. Mock `remember_fact` success → `PROMPT_SUPPLIED`, `reviewed=true`, seam called; agent reply may confirm.
3. Mock seam reject → tool `ok: false`; reply must not claim memory.
4. `write_memory` with leftover proposals in old fixtures → no persist of that field (field removed).
5. Eval YAML: remember / forget / ephemeral / constraint / commitment (`eval/scenarios/memory.yaml`).
