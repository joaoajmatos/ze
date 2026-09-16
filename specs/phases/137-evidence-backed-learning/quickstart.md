# Quickstart: Evidence-Backed Goal Learning

Phase 136 must be implemented and expose usable ActionRecords before these checks run. No real OpenRouter calls are required.

## Test sequence

From the repository root:

```bash
make test-automation
make test
make test-web
make lint
```

Run the migration suite or the focused Alembic migration test documented in `docs/testing.md` before the application/API suites.

## Expected checks

- An automated learning cannot persist without an ActionRecord evidence link.
- One action record, retries from the same lineage, or multiple claims from one milestone fail the diversity gate.
- Two consistent independent execution contexts create an eligible `INFERENCE`; repeated model summaries do not produce a FACT.
- User confirmation is durable evidence and can support a FACT only for the statement the user confirmed.
- Contradiction marks a claim `review_needed`; rejection/correction retains history and removes it from normal consumers.
- Planner, executor, and priority consumers receive only active eligible claims, with INFERENCE labels.
- Goal detail/review API exposes evidence summaries and lifecycle without raw ActionRecord payloads.
- No source code reads/writes `goals.learnings` or `goal_learnings` after the migration.

## Manual check (optional)

1. Start the development stack with a migrated database.
2. Complete two distinct verified goal actions that support a reusable pattern.
3. Open the goal detail, inspect the learning’s evidence count and tentative claim-kind label.
4. Review the learning: approve, correct, or reject it; verify history remains visible.
5. Confirm a retracted learning does not appear in a later planning-context trace or priority context.
