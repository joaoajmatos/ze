# Tasks: Speech-Act System One

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md). **Tests**: required, fail-first, mocked clients.

## Phase 1: Setup

- [x] **T001** Config: `system_one.surfaces.speech_act` (off, bars documented uncalibrated) · `apps/ze-api/config/config.yaml`

## Phase 2: User Stories 1–3 (P1/P1/P2) — one gate serves all three

- [x] **T002** Fail-first: reminder / forget-vs-cancel / durable fact / unknown label / low peakedness / even biography / non-keep family / skip fallback / trivial turn / surface off / consumed flags / threshold parsing · `core/cognition/ze-memory/tests/test_speech_act_system_one.py`
- [x] **T003** Questions (eight-way act incl. PT examples, family, biography), `AdmissionThresholds`, `thresholds_from_settings`, `decide`, `judge_admission` · `core/cognition/ze-memory/ze_memory/speech_act_gate.py`
- [x] **T004** Gate `gather_fact_proposals`: hold → `[]` (no Haiku), admit → narrow wording call, skip → legacy extractor once · `core/cognition/ze-memory/ze_memory/extractor.py`
- [x] **T005** Fail-first: admission judgments land on the recorded `MessageTrace` · `core/engine/ze-core/tests/orchestration/nodes/test_extractor_dual_write.py`
- [x] **T006** Per-turn judgment sink + attach to `message_trace` · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`

## Phase 3: Polish

- [x] **T007** `make test-memory`, `make test-core` green; ruff clean on touched files
- [x] **T008** Index/status: spec status, `specs/README.md`, `CLAUDE.md` phase row, arch note
- [ ] **T009** (follow-up, not this phase) Calibrate the three bars on Ze fixtures incl. Portuguese, then flip the surface on
