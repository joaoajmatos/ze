# Contract: Specialist instruction family

Pinned identifiers: `remember_fact`, `forget_fact`, “I remember that you…”, Principle VIII.

## Shared family (MUST)

Calendar, messenger, and news `_AGENT_INSTRUCTIONS` MUST include the same rules as companion’s 141 memory-use block, in substance:

- Apply retrieved facts silently when they change the domain answer.
- Do not announce “I remember that you…” or dump biography unsolicited.
- If the user asks what Ze knows about them, answer from the biography/context block without claiming a memory **write**.
- Do not claim `remember_fact` or `forget_fact` success; those tools are not on this agent.

## MUST NOT

- A specialist-only paragraph that still treats “I remember that you…” as acceptable style.
- Documenting `remember_fact` / `forget_fact` as available tools.
- Adding those names to `CalendarAgent.tools`, `MessengerAgent.tools`, or `NewsAgent.tools`.
- Rewriting prospecting, goals, workflows, or reminders in this phase.
- Teaching specialists to **block** mail/calendar writes from constraint facts (Phase 144).

## Domain job (MUST keep)

Operational guidelines (ISO times, send rules, news grounding) remain. Memory constitution does not replace them or push them below biography (see `prompt-order.md`).

## Tests code against

- Catalog listings exclude `remember_fact` and `forget_fact`.
- Instruction strings contain silent-use / no-unsolicited-framing language and do not instruct the model to confirm remember-tool success.
