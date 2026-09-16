# Quickstart: Action Instrumentation

## Prerequisites

- Phase 135 ActionRecord ledger is implemented and exposes an injected validated recorder.
- The producer’s domain table/store already persists an identifiable source record.
- Test environment uses mocks for providers, asyncpg, and the ledger recorder.

## Implement one producer safely

1. Locate the code point where the domain record has its factual outcome.
2. Construct the stable source-derived idempotency identity.
3. Collect available context IDs from the call scope and durable source record.
4. Submit the truthful Phase 135 lifecycle and, for a terminal record, its outcome through the
   Phase 135 recorder. Use `started` or `in_progress` with no outcome for a pending attempt.
5. If the recorder call fails after the domain write, retry it with the same source/key; do not re-run the action.

## Minimum test matrix

For every producer family, add tests covering:

- one successful terminal outcome;
- one relevant non-success outcome;
- a duplicate/replayed completion that leaves one ActionRecord;
- source citation and all available context IDs;
- no terminal success submission before the source outcome is known.

For a producer with asynchronous confirmation or provider settlement, also test:

```text
durable attempt → pending lifecycle observation → causally linked terminal observation
```

## Target validation

Run package tests for the touched producer and Phase 135’s ledger contract tests, for example:

```bash
make test-workspace
make test-calendar
make test-automation
make test-prospecting
make lint
```

Use actual Makefile targets available in the checkout; messenger tests may be part of its plugin target.

## Boundary check

Review the diff before shipping:

```bash
git diff -- core/ops/ze-workspace plugins/ze-messenger plugins/ze-calendar \
  core/automation/ze-automation plugins/ze-prospecting
```

It must not change inbound processors, `signal_sources()`, learning/procedure code, or priority/arbitration code. It must not add a direct ledger SQL writer or make ActionRecord a recovery source.
