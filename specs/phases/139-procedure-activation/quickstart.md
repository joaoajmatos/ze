# Quickstart: Governed Procedure Activation

Validate that Phase-138-governed procedures are discoverable as advisory context, explicit to invoke, capability-gated, and traceable.

## Prerequisites

1. Phase 138's procedure lifecycle migration, store, and review contract are implemented and migrated.
2. Install workspace dependencies and start the normal dev database when running integration checks.
3. Seed test fixtures for a validated/enabled procedure, a pending-review procedure, a disabled procedure, and a validated procedure with an unmet precondition.

## Automated validation

From repository root:

```bash
make test-memory
make test-core
make test-automation
make test-agents
make test
make test-web
make lint
make codegen
```

Run the relevant plugin targets for every agent integration selected by the registry audit in task T009. Tests use mocks for database and LLM paths.

Expect:

- Discovery returns only eligible validated/enabled versions as `ready`.
- Relevant procedures with missing prerequisites are marked `blocked` and cannot invoke.
- A selected procedure records its immutable id/version and step reference on every action trace.
- Procedure tool hints only narrow the agent/capability tool set.
- Capability-denied actions are not run but remain traceable.
- Completion records idempotent outcome feedback for Phase 138 review; it does not alter confidence directly.
- Editing creates a governed revision; disabling immediately removes a procedure from new actionable matches while preserving evidence and history.

## Manual validation (optional)

1. Start the development stack with `make dev-full`.
2. Open procedure management and confirm list rows visibly distinguish validated, pending-review, and disabled procedures.
3. Open a validated procedure; inspect trigger, preconditions, version, evidence, and recent activation outcomes.
4. Begin a task whose context satisfies the procedure. Confirm Ze can surface it as advisory guidance but no action occurs until an explicit agent/planner selection.
5. Inspect the resulting message/action trace. Confirm every guided action reports the selected immutable procedure version and step.
6. Disable that procedure. Re-run the same task and confirm it no longer appears as actionable guidance.
7. Submit an edit and verify the previous version remains visible from its evidence/outcome history.

## Caller and scope scan (T039–T040)

- Goal and workflow planners fetch guidance only through `ProcedureDiscovery.match`. There is no `memory.retrieve` fallback for procedures.
- Agents receive matches from `fetch_context` and must call `invoke_procedure` before tool narrowing. Matching does not execute steps.
- `signal_sources()`, contribution collision handling, and contribution arbitration were not changed in this phase.

## Validation results (T042)

- `make test-memory`, `make test-agents`, `make test-automation`, `make test-core`: pass.
- `apps/ze-api/tests/api/test_procedures.py`: pass.
- Procedure management widget test: pass.
- zm023 activation ledger is already in the ze-memory chain; no extra migration beyond that revision.


