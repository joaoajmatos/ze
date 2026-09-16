# Data Model: Parallel Per-Subtask Gates

No new tables. Additive graph state only.

| Field | Where | Meaning |
|---|---|---|
| `subtask_gate_decisions` | `AgentState` | List of `{agent, intent, decision}` aligned with `envelope.subtasks` for compound fan-out. Absent/empty on single-agent and conductor turns. |
| `gate_decision` | `AgentState` | Single-agent: unchanged. Compound: `BLOCKED` iff all subtasks BLOCKED; otherwise not used as a turn-wide min() to choose `draft_response`. |
| Confirmation | `pending_confirmations` | One row per AWAIT subtask, keyed by `request_id` (113). Payload identifies which subtask index/agent. |

`subtask_results` already exists; 158 may be a partial list until remaining AWAIT jobs finish.
