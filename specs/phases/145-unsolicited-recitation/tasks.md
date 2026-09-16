# Tasks: Response-Level Unsolicited Recitation

**Input**: [spec.md](./spec.md), [plan.md](./plan.md)

Tests: required (constitution V). Fail-first before the matching implementation wave.

---

## Phase 3: Recitation gate (US1 + US2)

**Wave 1 — independent (different files):**

- [x] **T001** [P] [US1] Fail-first: unsolicited “I remember that you…” stripped; asked recall may state facts; earned `remember_fact`/`forget_fact` `ok` confirmations kept; open-item / task-paraphrase / in-turn quote not stripped; recitation-only empty remainder is not `COULD_NOT_STORE` · `plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py`
- [x] **T002** [P] [US2] Fail-first: `CompanionAgent.run` passes `user_text`; `token_sink` still sees only gated text when the model recites unsolicited biography · `plugins/ze-personal/tests/agents/companion/test_companion_agent.py`
- [x] **T003** [P] [US1] Eval criteria: non-recall recitation vs explicit recall question · `eval/scenarios/memory.yaml`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2:**

- [x] **T004** [US1] Extend `enforce_memory_confirmations` with conservative recitation framing, optional `user_text` asked-recall exemption, and unchanged 143 `ok` confirmation rules · `plugins/ze-personal/ze_personal/agents/companion/honesty.py`

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3:**

- [x] **T005** [US1] Pass the latest user message into the gate from `CompanionAgent.run`; keep the existing `token_sink` buffer; do not re-home `TurnSurfacing` or add a 144 veto · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

---

## Polish

**⟶ Wait for Wave 3 to finish, then:**

**Wave 4:**

- [x] **T006** Validate against Success Criteria — `make test-personal` · `plugins/ze-personal/tests/agents/companion/`

---

**Depends**: Wave 1 → T004 → T005 → T006.
