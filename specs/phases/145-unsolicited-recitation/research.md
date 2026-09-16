# Research: Response-Level Unsolicited Recitation

**Feature**: `145-unsolicited-recitation`  
**Date**: 2026-09-16

## 1. Where to enforce

**Decision:** Extend `enforce_memory_confirmations` on the companion turn path. `run` already buffers `token_sink`; `stream` already delegates to `run`.

**Rationale:** FR-001/FR-005 — a new prompt paragraph already failed in 141. A second gate module is a dual door.

**Rejected:** Graph-node rewrite; specialist dialect in this phase; LLM rewrite of the reply; lifting the gate into `ze_agents` (144: dialects stay out of `ze-agents`).

## 2. Asked recall vs recitation

**Decision:** Optional `user_text` argument. If the user asked what Ze knows or named a stored fact, skip recitation stripping. Do not skip 143 unearned store/forget claims.

**Rationale:** FR-002.

**Rejected:** Inferring recall only from the model reply.

## 3. Fallback copy

**Decision:** Recitation-only drops must not use `COULD_NOT_STORE` / `COULD_NOT_FORGET`. If nothing remains, a short non-biography acknowledgement.

**Rationale:** Those fallbacks would lie about the store.

## 4. Out of scope

Phase 144 veto. `TurnSurfacing` ownership. Specialist catalog rewrite (149).
