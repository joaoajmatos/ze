# Data model: Promote conductor instance

No new tables. Uses existing Goal and Workflow rows.

## Promote offer (turn-local / trace)

| Field | Meaning |
|---|---|
| `conductor_promote_offered` | bool on `MessageTrace` or ledger sidecar |
| `conductor_promote_kind` | `goal` \| `workflow` \| `ask` |

## Unfinished ledger

A ledger is unfinished if any item status is not terminal (`done`, `skipped`, `denied`).

Same-reply auto-offer: unfinished and the turn is **not** already closing with 156 `ask_user`. Timeout/abort: offer whenever unfinished, including `ask_user` / `awaiting_confirmation`.

## Create brief (151)

`delegate_to_agent` to `goals` (`create` intent) or `workflow` (`manage` intent) with `objective` = continue this job, `prior_outputs` = ledger + specialist outputs, `inputs` = original user prompt.

## Forbidden

`memory_procedures` writes; procedure activation records.
