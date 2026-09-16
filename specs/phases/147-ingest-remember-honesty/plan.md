# Implementation Plan: Ingest vs Remember Honesty

**Branch**: `147-ingest-remember-honesty` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

## Summary

`MemorySink` still writes synthesized perception facts on file ingest. That is not `remember_fact`. Phase 143 already strips remember-tool success language unless that tool returned `ok` true, but companion/ingest copy can still sound like biography remember, and eval has no ingest fixture that fails an unearned remember claim.

Keep the sink. Reuse `enforce_memory_confirmations` (same `ok` payload) on companion. Tighten ingest and companion copy. Hard-cut eval so ingest success is not scored as remember-tool success. Do not import `ze_personal` from `ze-ingestion`.

## Key Decisions

**Decision:** Do not change `MemorySink.push` or add a remember API.  
**Why:** Spec FR-004 / R7 / Principle VIII — ingest stays a synthesized perception write.  
**Rejected:** Routing ingest facts through `remember_fact`, or a second “ingest remember” tool.

**Decision:** Reuse Phase 143 `enforce_memory_confirmations` on companion only. `IngestionAgent` must not import `ze_personal`. Hard-cut ingestion instructions and `ingest_url` / `ingest_text` copy. Do **not** lift claim dialect into `ze_agents` (144 pin).  
**Why:** Ingest-only turns have no earned remember; companion is the gated chat speaker; `ze-ingestion` cannot take a plugin dependency.  
**Rejected:** Importing companion honesty from `ze_ingestion`; lifting the gate into `ze_agents`; treating `ingest_url` / `ingest_text` success as earned remember.

**Decision:** Allow ingest/extraction acknowledgements (“ingested the PDF”, “extracted N facts”, archive language). On a mixed turn, keep earned biography confirmation; drop sentences that claim the file as a whole was stored via `remember_fact`.  
**Why:** US1 scenario 3 and 143 mixed-extra already forbid inventing extra memory; file-as-whole confirmation is the ingest-shaped version.  
**Rejected:** Confirming the document whenever any `remember_fact` `ok` landed this turn.

**Decision:** Add/hard-cut eval in `eval/scenarios/memory.yaml` against `tool_calls` / ingest outcome, not `memory_proposals_count`.  
**Why:** FR-003 / SC-002; Phase 150 owns deleting that field.  
**Rejected:** A dual grader that accepts “I’ll remember” after ingest.

**Decision:** No new `contracts/` — consumers still code against the 143 earned-confirmation gate.  
**Why:** Simple size; no new public identifiers.  
**Rejected:** A second contract that restates `ok`.
