# Contract: Specialist prompt order

Pinned identifiers from the spec’s Verbatim Constraints: `_build_system_prompt`, `_format_memory`, `ze_sdk`, `ze_core`.

## Assembler

Calendar, messenger, and news MUST call `BaseAgent._build_system_prompt` (no plugin-local copy of the assembler). `_format_memory` stays on `BaseAgent`; specialists MUST NOT reimplement fact-line formatting.

## Order invariant

In the assembled system prompt for each of the three agents:

1. A unique constitution marker (`## Memory constitution` / `MEMORY_CONSTITUTION` body) MUST appear before the agent job text.
2. The agent job text MUST appear before `## Retrieved biography` when biography is present.
3. Empty biography: constitution and job still lead; tests MUST NOT require a biography heading.

## Tests code against

- Calendar job snippet (e.g. ISO-8601 / `{timezone}`) still present and not after biography.
- Messenger job snippet (send/list rules) still present and not after biography.
- News job snippet (store freshness / candidates / no invented headlines) still present and not after biography.
- Identity builder that injects `## Retrieved biography` + a fact value: fact value appears after the job snippet.
