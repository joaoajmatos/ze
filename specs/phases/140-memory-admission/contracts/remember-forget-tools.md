# Contract: remember_fact / forget_fact

Identifiers pinned by spec verbatim constraints.

## `remember_fact`

- **Access**: `ToolAccess.WRITE`
- **Agent**: companion only (this phase)
- **Args**: `predicate: str`, `value: str`
- **Behavior**: Submit one perception `FACT` contribution via `submit_perception_facts` with `Provenance.PROMPT_SUPPLIED`, `reviewed=true`. Must not skip seam/NLI.
- **Result**: `{"ok": true, "id": "<uuid>"}` on persist; `{"ok": false, "error": "<message>"}` on seam/store/NLI failure.
- **Confirmation rule**: Companion may tell the user the fact is remembered only when `ok` is true.

## `forget_fact`

- **Access**: `ToolAccess.WRITE`
- **Agent**: companion only (this phase)
- **Args**: `query: str` (natural language or predicate)
- **Behavior**: Resolve to one or more non-contradicted facts; mark contradicted. If none match, `ok: false`.
- **Result**: `{"ok": true, "ids": ["<uuid>", ...]}` or `{"ok": false, "error": "..."}`.
- **Confirmation rule**: Claim forgotten only when `ok` is true.

## Removed contract

`AgentResult.memory_proposals` is not a persist API. Callers must not pass it to `write_memory` for storage.
