# Contract: Promote conductor instance

Identifiers: `delegate_to_agent`, `prior_outputs`, `create_goal`, `create_workflow`, `memory_procedures` (forbidden), `conductor_ledger`, `request_id`, Principle VIII.

## Agents

- Goal specialist name: `goals`
- Workflow specialist name: `workflow`

## Timeout / abort / turn-end unfinished

MUST offer, MUST NOT insert. Copy MAY extend the existing confirmation timeout assistant message.

## Create

MUST be nested tools `create_goal` or `create_workflow` after companion `delegate_to_agent`. MUST NOT be called from companion’s tool list.

## Tests code against

- Unfinished ledger → offer, 0 store creates.
- Accept → one nested create tool; companion still `primary_agent`.
- Timeout with ledger → offer language; 0 creates.
- Successful all-`done` conductor → 0 offer.
- Grep promote implementation files: no `memory_procedures`.
- Eval id `conductor_promote_offer_unfinished` (or equivalent).
- 155 mixed rewrite and 156 caps still in force.

## In-chat pin

Workflow/goal engines MUST NOT become the user-facing speaker for the originating chat turn.
