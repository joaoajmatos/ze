# Contract: Action Producer Instrumentation

Internal Python contract. Phase 135 owns the concrete `ActionRecord` type, store, migration, and seam implementation. This contract pins what each producer must provide.

## Producer submission

```python
async def record_action(
    *,
    action_type: str,
    lifecycle: ActionLifecycle,
    outcome: ActionOutcome | None,
    authoritative_ref: AuthoritativeRef,
    idempotency_key: str,
    occurred_at: datetime,
    summary: str,
    context: ActionContext,
) -> ActionRecord:
    ...
```

The actual Phase 135 API may differ in naming, but it MUST preserve these semantics:

1. Validate Action’s licensed contribution shape.
2. Append once or return the existing immutable observation by `idempotency_key`.
3. Represent a pending action with Phase 135's non-terminal lifecycle and append one causally linked terminal observation when it resolves.
4. Return the canonical ledger record.

Producers MUST call this injected contract or its Phase 135 adapter. They MUST NOT issue ledger SQL directly.

## Required values

```python
ActionOutcome = Literal[
    "success",
    "failure",
    "cancelled",
    "partial",
    "timeout",
    "unknown",
]
```

`ActionLifecycle`, `ActionOutcome`, `AuthoritativeRef`, and `ActionContext` are the types defined
by Phase 135. `AuthoritativeRef` requires the producer-owned `domain` and durable `record_id`;
the `ActionRecordDraft` also names its actor and producer plugin/core package. `ActionContext`
carries the optional durable request/correlation IDs named in [data-model.md](../data-model.md).
A pending action maps to Phase 135's non-terminal lifecycle and has no terminal outcome value.

## Call-site contract

| Producer | Must record | Terminalization rule |
|---|---|---|
| Workspace runs | command/file run result | after run persistence knows success, failure, or cancellation |
| Outbound messenger sends | send/attempt result | after provider result; pending only for durable unresolved dispatch |
| Calendar mutations | create/update/delete result | after local/provider mutation outcome |
| Reminder mutations | create/update/delete/schedule result | after durable mutation outcome |
| Goal execution | traceable action result | after execution trace outcome |
| Workflow execution | run/step result | after run/trace terminalization |
| Prospecting outreach | outreach attempt result | after outreach outcome |

## Idempotency

Each producer derives:

```text
{producer_kind}:{source_record_type}:{source_record_id}:{action_kind}:{observed_lifecycle}
```

The format may be encoded by Phase 135, but the components are mandatory. Callback/retry attempts reuse this key. A new durable source record is a new action identity.

## Chronology

- Do not write `success`, `failure`, `cancelled`, or `partial` before observing that state.
- A pending row retains its original `occurred_at`; resolution is a new immutable terminal observation causally referencing it.
- Instrumentation failure after domain persistence is retried against the same source/key. It must not repeat the side effect.

## Forbidden producer behavior

- Use ActionRecord as the domain action state or recovery source.
- Emit a record for inbound perception.
- Convert cancelled into failure.
- Duplicate a pending or terminal observation on replay. A causally linked terminal observation after a genuinely pending observation is required by Phase 135’s append-only model.
- Add shims or dual operational history for superseded producer callbacks.
- Interpret records into learning, procedures, priorities, or arbitration.
