# Contract: Ingest is not remember-tool success

- File ingest / `MemorySink` writes MUST NOT be presented as `remember_fact` success.
- Remembered confirmations remain gated on companion `remember_fact` payload `ok` true (Phase 143).
- `ze-ingestion` MUST NOT import `ze_personal` and MUST NOT move claim dialect into `ze_agents`.
- User-visible ingest copy MUST use ingest/extraction language.
- Eval MUST fail remember-tool claims on ingest-only turns.
- Judges use `tool_calls` / ingest outcome, not `memory_proposals_count` (field deletion is 150).
