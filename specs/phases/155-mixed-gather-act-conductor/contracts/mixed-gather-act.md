# Contract: Mixed gather+act → conductor

Identifiers: `apply_conductor_rewrite`, `is_sequential`, `delegate_to_agent`, `prior_outputs`, `inputs`, `conductor_hint`, `conductor_ledger`, `read`, `create`, `update`, `delete`, `send`, Principle VIII.

## Rewrite (normative)

```text
sequential_multi = envelope.is_sequential and len(envelope.subtasks) > 1
mixed = distinct_agents(subtasks) > 1 and has_gather(intents) and has_act(intents)
if sequential_multi or mixed:
    hint = envelope.subtasks
    envelope = companion primary, user prompt, not compound
    # is_sequential True on rewritten envelope (153 behavior)
```

MUST NOT use an allowlist whose only members are `research` and `messenger`.

## Tests code against

- Sequential multi still companion (existing 153 test).
- Independent all-read compound still identity (existing test).
- Sequential one subtask still specialist (existing test).
- **New:** `is_sequential=False`, research `read` + messenger `create` → companion + hint.
- **New:** `is_sequential=False`, research `read` + messenger `send` → companion.
- **New:** calendar `read` + messenger `create`, sequential false → companion (proves not a two-name list).
- **New:** research `read` + news `read`, sequential false → identity.
- **New:** two `create` specialists, sequential false → identity.
- Eval id `conductor_mixed_gather_act_research_messenger` present; 154 ids still present.
- Grep: `plan_sequential` still absent.

## Out of contract this phase

Parallel per-subtask gates; stall statuses; workflow/goal rows.
