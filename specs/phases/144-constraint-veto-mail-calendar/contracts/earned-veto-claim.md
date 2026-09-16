# Contract: Earned veto claim

Identifiers: “I won’t send that because of your constraint”, `ok`, `send_email`.

## Earned

`earned_veto` iff some this-turn `ToolCall` has payload `veto` true (mapping or JSON object). Missing/unparsable is not earned.

## Rules

1. If not `earned_veto`, user-visible text MUST NOT claim Ze refused/held because of a standing constraint (`I won’t send`, `I will not schedule`, `because of your constraint`, close equivalents).
2. Strip claiming sentences; fallback honest miss if the remainder is empty (`I could not apply that constraint.`).
3. Ordinary “got it” without a veto claim remains.
4. Companion and in-tree agents that can emit this dialect apply the gate on the same turn path as Phase 143 (including buffered `token_sink`). No prompt-only satisfaction.

## Tests code against

- Unearned “I won’t send that because of your constraint” → stripped/fallback.
- After `{veto: true}` → claim may remain.
- Sink never received the lie first.
