# Tasks: Ingest vs Remember Honesty

## Phase 2: Foundational

**Wave 1:**

- [x] **T001** [US1] Extend `enforce_memory_confirmations` so ingest/file-as-whole remember-tool claims are not earned from `MemorySink` or from a sibling `remember_fact` `ok` on a different preference · `plugins/ze-personal/ze_personal/agents/companion/honesty.py`

## Phase 3: User Story 1 — ingest is not “I’ll remember that”

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — independent (different files):**

- [x] **T002** [P] [US1] Companion copy: ingest acknowledgements in ingest/extraction language; mixed turn may confirm only the earned preference, not the file as a whole · `plugins/ze-personal/ze_personal/agents/companion/agent.py`
- [x] **T003** [P] [US1] IngestionAgent instructions and `ingest_url` / `ingest_text` descriptions: confirm ingest/extraction, never `remember_fact` success; do not import `ze_personal` · `core/ops/ze-ingestion/ze_ingestion/agent.py`
- [x] **T004** [P] [US2] Hard-cut/add ingest eval: fail remember-tool claims without `remember_fact` `ok`; pass honest ingest acknowledgements; judge `tool_calls` / ingest outcome, not `memory_proposals_count` · `eval/scenarios/memory.yaml`
- [x] **T005** [P] [US1] Align ingest docs that still equate ingest with remember-tool success (e.g. “watch this video and remember it”) · `docs/ingestion.md`

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3:**

- [x] **T006** [US1] Unit tests: ingest language allowed; remember-tool claim without `ok` stripped; mixed ingest + earned preference does not confirm the file · `plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py`

## Phase 4: Polish

**⟶ Wait for Wave 3 to finish, then:**

**Wave 4:**

- [x] **T007** Validate SC-001/SC-002 — `make test-personal`

Do not edit `core/ops/ze-ingestion/ze_ingestion/sink.py` except to leave `MemorySink` as synthesized perception (FR-004).

**Depends:** T001 → T002–T005 → T006 → T007.
