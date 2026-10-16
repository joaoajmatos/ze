# Quickstart: validating 181

## Prerequisites

`make install`, `make db-up`, `make migrate` (applies `zc033`, `zc034`), `make web-install`.

## Automated gates

```bash
make test-agents        # ToolSpec rules, call_tool resolution order, agentic_loop park/resume, delegate park
make test-core          # graph: preflight, await_write_confirmation, compound park, restart via real serde, budget pause
make test-memory        # constraint veto evaluate() at park time
make test-automation    # pre-approval, held writes, goal executor hold, workflow graph hold
make test-workspace     # workspace ask_check
make test-calendar test-messenger test-personal test-finance test-prospecting test-news test-ingestion test-worldstate test-priority
make test               # ze-api: WS frames, handle_confirm, timeout-as-deny, supersede, held-write REST, eval confirm
make test-sdk           # boundary test; SDK exports (Mode/Intent gone, AskDecision added)
make test-pg            # held_writes store, migration zc033 on real Postgres
make test-web typecheck-web
make lint
```

Search check (SC-007): `rg -n "\bIntent\(|\bMode\b|intents =|default_mode|_primary_intent|CapabilityGate|session_overrides|capability_overrides|GateDecision|ToolConfirmationRequired|tool_interrupt_fn|workspace_confirmed|is_draft" --type py --type ts -g '!**/migrations/**'` returns nothing.

## Manual run (`make dev-full`)

1. Chat "delete my 3pm" (seeded calendar or a real test calendar). Expect one confirmation card: "delete a calendar event — <title> <time>". Before approving, the event still exists. Approve: the event is gone; the reply says so; the trace panel shows "Confirmations: delete_event — approved".
2. "what's on tomorrow and email Ana the agenda": one card after the read finishes; Deny all: the reply lists tomorrow and says "Okay, I didn't send an email".
3. Ask for an email, Approve with an edited body: the sent email has the edited body.
4. Leave a card open past `CONFIRM_TIMEOUT_SECONDS` (set 30 in `.env` for the test): a "didn't" reply arrives; nothing ran.
5. Create a weekly workflow that emails a summary: the creation card lists "Step N (messenger) may: send an email". Trigger it: no card for the email. Edit its steps: the next approval lists them again.
6. A workflow step that tries an un-pre-approved write: the run shows `held`, a push arrives, the notification has Approve/Deny; Approve resumes it.
7. With a reviewed constraint "no meetings before 10", "book a call with Rui at 9": the card shows the conflict on the item; one card only.

## Evals (`make dev-eval`, `make eval-server`)

`python eval/run.py --tag confirmation` runs `eval/scenarios/write_confirmation.yaml` (delete my 3pm, send Ana the notes, compound read + send, conductor delegation, deny). All pass: a confirmation opens, zero asks-first tools run before the `confirm` step.
