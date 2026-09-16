# Data Model: Action Instrumentation

Phase 135 owns the persisted `ActionRecord` ledger. This phase supplies producer values to that model; it does not create a second table.

## ActionRecord

| Field | Semantics in this phase |
|---|---|
| `id` | Ledger identity supplied by Phase 135 |
| `idempotency_key` | Stable producer-kind/source-record/action-kind/observed-lifecycle identity |
| `action_type` | Producer-owned action label defined by Phase 135 |
| `lifecycle` | `started`, `in_progress`, `succeeded`, `failed`, `cancelled`, `partial`, `timed_out`, or `unknown` |
| `outcome` | Terminal only: `success`, `failure`, `cancelled`, `partial`, `timeout`, or `unknown` |
| `occurred_at` | Time this action observation occurred; terminal resolution time for a pending attempt |
| `created_at` | Ledger append timestamp supplied by Phase 135 |
| `authoritative_ref` | Producer package plus durable source record reference |
| `summary` | Factual, non-interpretive outcome description |
| `context` | Phase-135 typed request/correlation IDs available to the producer |
| `contribution` | Action’s validated ledger/seam envelope from Phase 135 |

## Producer outcome state model

```text
new durable action ──► pending observation ──► terminal observation
                                                    ├── success
                                                    ├── failure
                                                    ├── cancelled
                                                    └── partial
```

- A pending observation is represented by Phase 135's non-terminal `started` or `in_progress`
  lifecycle and has no terminal `ActionOutcome`. A terminal observation is appended with a causal
  reference to that observation; the ledger is immutable and has no in-place transition.
- Phase 135 owns the closed terminal `ActionOutcome` vocabulary, including `partial` where a
  single durable producer operation has mixed results. Producers use `unknown` or `timeout` when
  those are the factual terminal observations.
- A producer that knows a final outcome at first observation emits only the terminal record.

## Source reference

The source reference is a typed pair:

| Field | Rule |
|---|---|
| `producer_kind` | One of workspace, messenger, calendar, reminder, goal, workflow, prospecting |
| `source_record_id` | ID of the authoritative producer record |
| `source_record_type` | Stable domain type, such as `workspace_run`, `outbound_message`, `goal_execution_trace` |

The source record must already exist before a terminal success/failure/cancelled/partial record is submitted. A durable pending request may cite its durable request/attempt row.

## Context IDs

All are optional except the source reference and idempotency key. Producers populate those available without manufacturing values.

| Group | IDs |
|---|---|
| Turn | `session_id`, `message_id`, `thread_id` |
| Automation | `goal_id`, `milestone_id`, `workflow_id`, `workflow_run_id` |
| Workspace | `workspace_run_id` |
| Messaging | `channel_id`, `outreach_id` |
| Scheduling | calendar event/mutation ID, `reminder_id` |

## Producer-specific mapping

| Producer | Source record type | Minimum context |
|---|---|---|
| Workspace | `workspace_run` | `workspace_run_id`, session/message when present |
| Messenger | `outbound_message` or durable send attempt | `channel_id`, thread/session/message when present |
| Calendar | calendar mutation/event record | calendar event/mutation ID, session/message when present |
| Reminder | reminder record/operation | `reminder_id`, session/message when present |
| Goals | `goal_execution_trace` | `goal_id`, `milestone_id`, session/message when present |
| Workflows | workflow run or execution trace | `workflow_id`, `workflow_run_id`, session/message when present |
| Prospecting | `prospect_outreach` | `outreach_id`, channel/campaign context when present |

## Integrity rules

1. Unique idempotency identity enforces exact-one record per durable producer outcome observation.
2. A replay may return the existing pending or terminal observation. A later terminal result after pending appends one causally linked immutable observation.
3. `success` requires an observed successful source outcome; `failure`, `cancelled`, and `partial` require their corresponding source evidence.
4. Context can be absent, but source citations cannot be fabricated.

## Out of model

- Producer domain state, provider receipts, retry scheduling, and recovery ownership
- Inbound/perception records and signals
- Interpretations, learning artifacts, procedures, priorities, and arbitration decisions
