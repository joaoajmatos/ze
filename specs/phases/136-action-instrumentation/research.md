# Research: Action Instrumentation

## R1. Record after a factual outcome

**Decision:** Record only after the producer has a durable factual outcome. The sole early record is `pending`, used when a durable request/attempt exists but its final result is unknown.

**Rationale:** An action ledger must describe what happened, not what Ze intended to do. Recording success on dispatch makes provider failures look successful and destroys audit value.

**Rejected:** Recording at action invocation and appending corrective rows later. It creates contradictory double-history and violates exact-one semantics.

## R2. Domain source records are canonical

**Decision:** Every action record points to a producer-owned durable source record. The domain record remains authoritative for lifecycle, recovery, provider details, and retries.

**Rationale:** Workspace, channels, calendar, automation, and prospecting each contain domain-specific semantics. A shared ledger is a cross-domain evidence spine, not a replacement abstraction.

**Rejected:** Making ActionRecord the source used by retry/recovery code. This would duplicate domain state and cause ownership inversion.

## R3. Stable source-derived idempotency

**Decision:** Use `producer_kind + source_record_id + action_kind` as the conceptual idempotency identity. Persist/reconcile through Phase 135’s unique/upsert contract. Callback IDs, timestamps, and provider polling attempts are never identity.

**Rationale:** A source row survives restart and tells repeated completions from a distinct action. It enables retrying ledger persistence independently from the side effect.

**Rejected:** Random ledger IDs or deduping on payload text/timestamps. Neither survives replay reliably.

## R4. Outcome taxonomy and transition

**Decision:** Phase 135 owns the closed lifecycle/outcome vocabulary. A non-terminal pending
attempt uses `started` or `in_progress` with no outcome; terminal observations use `success`,
`failure`, `cancelled`, `partial`, `timeout`, or `unknown`. The ledger remains append-only: a
pending observation is followed, when known, by one causally linked terminal observation.

**Rationale:** Cancellation is a real result distinct from failure. Partial applies to a singular durable producer action with mixed observable effects, not to unrelated batch members.

**Rejected:** Treating cancelled as failure or mutating a Phase 135 append-only row on pending resolution.

## R5. Context is opportunistic and factual

**Decision:** Capture all context IDs available at the producer boundary, without inventing values: conversation `session_id`, `message_id`, `thread_id`; automation identifiers; channel/outreach identifiers; source record ID; calendar/reminder or workspace run IDs.

**Rationale:** A record can be navigated and audited without a reverse-join guess. Optional fields support producers that originate outside a conversational turn.

**Rejected:** Requiring every context field. Background jobs and provider callbacks legitimately lack some turn context.

## R6. Producer mapping

**Decision:** Map terminal producer lifecycle points as follows:

| Producer | Durable cited source | Natural action point |
|---|---|---|
| Workspace | workspace run | run completes, fails, or cancels |
| Messenger | outbound send/attempt | provider send result or durable pending dispatch |
| Calendar | calendar mutation/event operation | provider/local mutation outcome |
| Reminder | reminder operation/record | create/update/delete/schedule outcome |
| Goals | goal execution trace | step/milestone action outcome |
| Workflows | workflow run/execution trace | step/run terminalization |
| Prospecting | outreach record | send/attempt result |

**Rationale:** Each point has both the domain result and the identifiers required for ledger citation.

## R7. Failure posture

**Decision:** A recorder failure after source persistence is retryable and observable, but it does not reverse or repeat the producer side effect. A recorder failure before source persistence cannot yield a success record.

**Rationale:** Ledger availability should not make completed external actions disappear, nor should it induce duplicate outbound effects.

## R8. Explicit exclusions

This phase does not treat inbound events as actions, alter `signal_sources()`, infer lessons or procedures, or introduce arbitration. Those use the ledger as future evidence only when separately specified.
