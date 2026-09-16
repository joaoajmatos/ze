# Contract: Conductor observability and eval

Identifiers: `conductor.checking_calendar`, `conductor.drafting_mail`, `conductor_sequential_calendar_email`, `routing_independent_parallel_not_companion`, `conductor_speech_act_146_honest`, `conductor_mid_sequence_confirmation`, `request_id`, `MessageTrace`, `trace_update`, `prior_outputs`, `inputs`, Principle VIII.

## API / WS

`GET /api/v0/messages/{id}/trace` and `trace_update` MUST include conductor hint + ledger (nullable). Field names in OpenAPI MUST match codegen. Do not hand-edit only `ws.ts`.

## Progress

When companion `run_delegate` `agent_name=calendar` (read path) starts → emit `conductor.checking_calendar`.  
When companion `run_delegate` `agent_name=messenger` starts for draft/send → emit `conductor.drafting_mail`.

## Eval YAML

Scenario files under `eval/scenarios/` MUST define the four ids. Sequential scenario criteria MUST require:

- primary companion
- calendar tool then messenger tool (nested or sequential delegates)
- second delegate `prior_outputs` or `inputs` contains the event id from the first

Independent scenario MUST require primary ≠ companion.

## Tests code against

- Trace panel renders ledger + `request_id` from fixture.
- OpenAPI schema lists conductor fields.
- Grep eval YAML for the four ids.
- Progress unit test: key emitted on delegate start.
- `plan_sequential` still absent.
