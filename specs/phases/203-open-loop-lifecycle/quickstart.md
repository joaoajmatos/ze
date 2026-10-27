# Quickstart: validating phase 203

Run everything from the repo root of the floor checkout. No dev database is touched: `make test-pg` starts its own Postgres container (or uses `ZE_TEST_PG_URL`, which must name a throwaway `ze_e2e_*` database, never the shared `ze` one).

## 1. Rules and unit suites (no database)

```bash
make test-worldstate     # table test (70 event × state pairs), stamp-once check, callers against a mocked LoopLifecycle
make test-core           # write_memory calls configurable["loop_commit"]
make test                # ze-api: REST loops routes, wiring, tools
make lint
```

Expected: green. `test_lifecycle_rules.py` fails if any `(event, state)` pair is missing from `EVENT_RULES` or if `0.9` / the stamp fragment appears outside `lifecycle/rules.py`.

## 2. Real Postgres

```bash
make test-pg
```

Look for, in `apps/ze-api/tests/pg/`:

| File | Proves |
|---|---|
| `test_loop_lifecycle_pg.py` | every event against real rows (SC-004); each multi-write event with its second table forced to fail leaves the loop unchanged (SC-001, via the `ze_test_faults` trigger, research R9); decay after a sweep does not drift twice (US1-3); two promoters, one wins (edge case); confirm on an active loop raises the 409 error type |
| `test_loop_commit_pg.py` | `LoopInflow.commit` with each decision and a fake title writer (US3); the 30-day replay where no dropped or expired loop comes back (SC-005) |
| the existing loop pg tests | unchanged behavior through the new events (FR-013) |

## 3. Static checks

```bash
# no store write method survives (FR-007)
grep -nE "def (create|transition|resolve|link|link_entity|link_evidence|set_confidence|set_dismissed_evidence_fingerprint|set_drift_deadline|set_drift_rationale|record_corroboration|stamp_declared|add_source|promote|mark_source_promoted)\(" core/cognition/ze-worldstate/ze_worldstate/store.py   # expect nothing

# the closure, the remap and the threading are gone (FR-008, FR-009)
grep -rnE "commit_for|_LOOP_KIND|propose_loop_candidates|LoopGateDecision|_commit_admitted" core apps eval --include='*.py'   # expect nothing

# the declared stamp is defined once (SC-002)
grep -rn --include="*.py" "0\.9\b" core/cognition/ze-worldstate/ze_worldstate   # expect lifecycle/rules.py only
```

SC-003 (no commit-path function above 8 parameters) is checked by `test_commit_path_arity` in `test_admission.py`, which walks the functions `LoopInflow.commit` reaches by name and inspects their signatures.

## 4. Offline calibration shape checks

```bash
make calibrate-commitment-intake ARGS=--check-sets
make calibrate-loop-gate ARGS=--check-sets
```

Both offline and free. They prove the kind strings still line up after the rename.

## 5. Web

```bash
make test-web            # judgments.test.ts maps resolve / create_declared / create_suspected to the same sentences
make typecheck-web
```

## 6. Optional live regression (costs credits)

`make dev-eval`, then run `eval/scenarios/loops.yaml` through the eval server (`docs/eval.md`). Expected: the same pass set as on `main`.

## 7. Manual check on World (optional)

With `make dev-full`: drop a suspected loop on World, then re-send the same email through the dev inflow. The loop does not come back. Confirm a suspected loop: the row shows active, 0.9, a deadline seven days out.
