# Contract: EvalChatResponse without memory_proposals_count

## Remaining

Eval chat HTTP/MCP payloads MUST omit `memory_proposals_count`. Judges use `tool_calls` (`remember_fact` / `forget_fact`).

## Removed

- `EvalChatResponse.memory_proposals_count`
- Always-0 documentation of that field
- Dual “legacy” client field

## Guides (roadmap 151 bundled)

`AGENTS.md` and `CLAUDE.md` MUST agree on phases 140–150. Do not create `specs/phases/151-*`.
