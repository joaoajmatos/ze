# Quickstart: Perception Facts Seam

Verify listed writers persist facts only through the contribution seam. No live DB or LLM required for the default suite.

## Tests

From repo root:

```bash
make test-memory
make test-core
make test-ingestion
make test-automation
make test-onboarding
make test-messenger
make lint
```

If a short-name target is missing, use the package test target documented in `docs/testing.md`.

Expect:

- License-mismatched perception-fact submits reject before persist (mirror `test_ingest_signal_rejects_malformed_claim_kind_before_insert`).
- Mixed `write_memory` batch: explicit predicates `PROMPT_SUPPLIED`, others `SYNTHESIZED`.
- `MemorySink.push` with a UUID `ingestion_id` puts that id on `source_refs` / `EvidenceRef(kind="ingestion")`.
- Onboarding `memory_fact` still `reviewed=True` and `PROMPT_SUPPLIED`.
- `_promote_learnings` does not call ungated `propose_facts`; goal id is on evidence/`source_refs`.
- Existing PriorityView / `surface_loops` / resume-recap tests still pass without edits to those modules.

## Manual check (optional, dev stack)

1. `make dev-full`.
2. Complete a chat turn that should extract a preference; confirm a new memory fact appears (Memory feed) as before.
3. Ingest a small document; confirm facts appear and can be tied to the ingest id in logs or `source_refs`.
4. Confirm `/priority` and chat “still open” behavior is unchanged (Phase 132).
