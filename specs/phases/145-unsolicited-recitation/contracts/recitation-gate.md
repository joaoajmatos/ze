# Contract: Recitation gate

`enforce_memory_confirmations(response, tool_calls, user_text=None) -> str`

- MUST strip unsolicited biography recitation when `user_text` is not asked recall.
- MUST keep Phase 143 earned confirmations.
- MUST NOT treat `TurnSurfacing` open-item mentions as recitation.
- MUST NOT invent biography when the remainder is empty.
- Recitation-only empty remainder MUST NOT be `COULD_NOT_STORE` / `COULD_NOT_FORGET`.
- Callers that omit `user_text` stay strict (treat as non-recall).
- Implementation stays in companion `honesty.py` (not `ze_agents`).
- No second companion reply path.
