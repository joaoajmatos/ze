# Contract: Specialist remember-claim honesty

Pinned identifiers: `remember_fact`, `forget_fact`, Principle VIII, `ze_sdk`.

## Function (one door)

`enforce_memory_confirmations(response: str, tool_calls: list[ToolCall]) -> str`

Same semantics as Phase 143 (`specs/phases/143-memory-claim-honesty/contracts/earned-confirmation-gate.md`):

- `earned_remember` iff some call named `remember_fact` has payload `ok` true.
- `earned_forget` iff some call named `forget_fact` has payload `ok` true.
- Unearned remember/forget **success** sentences are stripped; empty remainder uses `I could not store that.` / `I could not forget that.`

Location: `ze_personal.agents.companion.honesty.enforce_memory_confirmations`. Calendar, messenger, and news import that function (news adds a `ze-personal` dependency). Do not lift it into `ze_agents`. Do not keep a second regex implementation.

## Specialist turn path

- `CalendarAgent.run`, `MessengerAgent.run`, and `NewsAgent`’s grounded loop MUST apply the function to model text before `AgentResult.response`.
- `stream` on those agents MUST NOT finish with an ungated remember/forget success claim (news already shares the grounded loop; calendar/messenger MUST gate collected stream text or delegate to gated `run`).
- Specialists have no remember/forget tools, so `tool_calls` will not earn those claims.

## Out of this contract (Phase 145)

Do **not** strip unsolicited biography recitation that is not a remember/forget **success** claim (e.g. “I remember that you like aisle seats” as recitation). Prompt constitution already forbids that framing; reply-path recitation enforcement is 145.

## Out of this contract (Phase 144)

Do **not** intercept `send_email` / calendar mutations from constraint facts.

## Tests code against

- Mocked specialist `run` whose model text is “I’ll remember that.” (no remember tool): user-visible `AgentResult.response` does not claim remember-tool success.
- Same for a forget-success claim without `forget_fact`.
- Catalog still excludes `remember_fact` / `forget_fact`.
