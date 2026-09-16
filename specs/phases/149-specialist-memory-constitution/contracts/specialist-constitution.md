# Contract: Specialist constitution (index)

Canonical detail lives in sibling contracts. This file is the checklist.

- Prompt order: [`prompt-order.md`](./prompt-order.md) — shared `_build_system_prompt`; no second builder.
- Instruction family: [`specialist-instructions.md`](./specialist-instructions.md) — silent use; no “I remember that you…” dialect; no remember tools on catalogs.
- Remember-claim honesty: [`remember-claim-honesty.md`](./remember-claim-honesty.md) — one `enforce_memory_confirmations` in companion honesty; specialists import it (news depends on `ze-personal`). Not a lift into `ze_agents`. Not Phase 145 recitation as a separate product.
- Plugin code imports `ze_sdk` / owning plugin, never `ze_core`.
- Constraint write-gating is Phase 144, not this spec.
