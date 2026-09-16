# Data Model: Specialist Memory Constitution (Phase 149)

This phase introduces **no stored entities**, tables, or migrations.

## Shared constitution (runtime string)

Already defined as `MEMORY_CONSTITUTION` on `BaseAgent` (Phase 141). Specialists inherit it through `_build_system_prompt`. Do not fork a second constitution string in plugins.

Logical fields (not a dataclass):

- Job-first: constitution and agent job precede retrieved biography
- Silent use: apply facts when they change the answer
- No unsolicited recitation **framing** in instructions (“I remember that you…”)
- Approximate treatment of inferred / low-confidence / stale lines (already in the shared block)

## Specialist job (instruction text)

Not persisted. Each plugin keeps its `_AGENT_INSTRUCTIONS`:

| Agent | Owning module | Job must still include |
|---|---|---|
| Calendar | `ze_calendar.agents.calendar.agent` | ISO-8601 times with offset, list/create/update/delete, timezone placeholder |
| Messenger | `ze_messenger.agents.messenger.agent` | list/get/draft/send/archive, plain-text mail, thread reply |
| News | `ze_news.agents.agent` | store freshness, candidate articles, no invented headlines |

Memory-use sentences on these jobs MUST match the shared constitution family. They MUST NOT document `remember_fact` / `forget_fact` as available tools.

## Remember API (absent)

`remember_fact` and `forget_fact` remain companion-only. Specialist catalogs MUST NOT list them. No new tool payload.

## Confirmation gate (moved, same contract as 143)

`enforce_memory_confirmations(response: str, tool_calls: list[ToolCall]) -> str`

- Earned remember iff a `remember_fact` call has `ok` true
- Earned forget iff a `forget_fact` call has `ok` true
- Specialists have neither tool, so remember/forget **success** claims are always unearned
- Does **not** model Phase 145 recitation (biography dump / “I remember that you…” as a recitation class)

No state transitions. Fallback copy remains `I could not store that.` / `I could not forget that.` when the gated remainder is empty.

## Prompt sections (logical order, unchanged assembler)

1. Current datetime
2. `MEMORY_CONSTITUTION`
3. Persona block (if identity builder supplies one)
4. Agent job (`_AGENT_INSTRUCTIONS`, plus existing extras already folded into the job string: skills, resume recap, screen, open priorities, procedures)
5. `## Retrieved biography` + formatted facts when present

Open items stay on `TurnSurfacing`. Constraint facts in biography are context only (Phase 144 veto is a later write intercept).
