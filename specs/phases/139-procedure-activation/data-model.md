# Data Model: Governed Procedure Activation

Phase 138 owns procedure lifecycle, revision, evidence, and confidence. Phase 139 adds the activation-facing model and references Phase-138 immutable versions.

## Procedure version (Phase 138)

Existing governed record, read by this phase.

| Field | Activation use |
|---|---|
| `procedure_id` | Stable procedure identity on match, invocation, trace, and feedback |
| `version` / revision id | Immutable guidance version selected by an invocation |
| `trigger` | Input to relevance matching |
| `preconditions` | Input to readiness evaluation |
| `steps` | Advisory step sequence and stable step references |
| `tool_hints` | Narrowing input only; never tool authority |
| lifecycle/review status | Eligibility filter |
| confidence | User-visible confidence and review input |
| evidence | Detail/review display and governed feedback context |

## ProcedureMatch

Ephemeral, not independently persisted.

| Field | Description |
|---|---|
| `procedure_version` | Eligible immutable version examined |
| `relevance` | Bounded candidate relevance used for ordering |
| `state` | `ready`, `blocked`, or `not_relevant` |
| `matched_trigger` | Explanation of why the task relates |
| `satisfied_preconditions` | Conditions supported by task context |
| `unmet_preconditions` | Required conditions missing or false |
| `effective_tool_names` | Intersection of current agent, capability, and procedure sets |

Validation: only lifecycle-eligible records may become `ready`; `effective_tool_names` must be a subset of each input set.

## ProcedureInvocation

Durable activation record; owned by the same package as the Phase-138 procedure lifecycle unless that phase already supplies an equivalent execution ledger.

| Field | Description |
|---|---|
| `id` | Stable invocation identifier |
| `procedure_id`, `procedure_version` | Immutable selected guidance |
| `origin` | Agent or planner name and turn/goal/workflow reference |
| `task_context_ref` | Existing trace/session/task reference, not a duplicated prompt |
| `state` | `started`, `completed`, `failed`, `cancelled` |
| `started_at`, `finished_at` | Lifecycle timestamps |
| `outcome_id` | Optional linked feedback record |

Validation: create only from a `ready` match; the selected version cannot be changed after creation.

## ProcedureActionLink

Trace enrichment, persisted with the existing action/tool trace or a normalized child record according to the current trace store.

| Field | Description |
|---|---|
| `invocation_id` | Parent invocation |
| `procedure_id`, `procedure_version` | Denormalized immutable provenance |
| `step_ref` | Stable step index/id from selected revision |
| `action_trace_ref` | Existing tool/action trace identifier |
| `capability_decision` | Allowed, denied, or awaiting confirmation outcome |
| `outcome` | Succeeded, failed, skipped, or not-executed |

Validation: every attempted procedure-guided action has exactly one link; a denied/blocked action remains traceable and has no execution result.

## ProcedureOutcomeFeedback

Durable, idempotent submission to the Phase-138 review/confidence intake.

| Field | Description |
|---|---|
| `id` | Feedback identity/idempotency key |
| `invocation_id` | One feedback summary per completed invocation |
| `procedure_id`, `procedure_version` | Version under review |
| `outcome` | Succeeded, partially succeeded, failed, cancelled, or blocked |
| `action_links` | References to action trace links |
| `summary` | Concise factual outcome summary |
| `submitted_at` | Submission time |

Validation: feedback does not directly change procedure confidence or lifecycle; Phase 138 consumes it.

## Relationships and transitions

```text
Phase-138 Procedure Version --eligible--> ProcedureMatch (ephemeral)
ProcedureMatch [ready + explicit selection] --> ProcedureInvocation
ProcedureInvocation --> ProcedureActionLink (one per guided action)
ProcedureInvocation [terminal] --> ProcedureOutcomeFeedback --> Phase-138 review/confidence intake
```

`started → completed|failed|cancelled`; feedback may be submitted once per terminal invocation. Disablement prevents new matches/invocations but does not invalidate historical links.

## Out of model

- Procedure extraction and lifecycle/review state transitions (Phase 138).
- New claim/contribution types, collision arbitration, signal polling, or multi-user access.
