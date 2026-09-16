# Quickstart: Action Record Ledger

## Prerequisites

- The Phase 134 contribution/fact hard cut is present.
- Postgres is running; apply the next `zm` migration with `make migrate`.
- Identify the current durable workspace-run and outbound-message source records before writing
  adapters. Do not infer success from an LLM tool trace.

## Validate the doctrine contract

```bash
make test-plugin
make test-memory
```

Expect:

- ACTION accepts `ACTION_RECORD` and rejects every other claim kind.
- Other source functions reject `ACTION_RECORD`.
- Missing/mismatched action payload, unsafe references, and invalid lifecycle/outcome pairs fail
  before insertion.

## Validate ledger persistence

```bash
make test-memory
```

Expect:

- Duplicate and concurrent submissions for one idempotency key return one immutable row.
- A changed payload under an existing key is rejected.
- A retry or correction creates another row with `retry_of` / `supersedes`.
- Query by authoritative and causal reference returns chronological evidence.
- No fact-store/embedding/contradiction code runs for ActionRecord tests.

## Validate producers and recovery

```bash
make test-workspace
make test-messenger
make lint
```

Expect:

- Workspace terminal outcomes and one outbound messenger action cite their existing source rows.
- Failure/cancel/timeout/unknown outcomes remain truthful.
- An injected ledger write failure is retried with the same idempotency key without rerunning the
  source action.
- There is no generic arbitration implementation and no `signal_sources()` change.

## Optional manual verification

1. Run a successful workspace command and inspect its source run plus linked ActionRecord.
2. Cause a non-zero workspace result and confirm a `failed` record holds only a sanitized summary.
3. Retry ledger delivery, not the command; confirm the same ActionRecord is returned.
4. Send one supported outbound message and verify that its source message still holds all
   communication detail while the ledger contains a citation only.
