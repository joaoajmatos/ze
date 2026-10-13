# Quickstart: Executive Repair

```bash
make test-worldstate        # drift predicate (unit), evidence plumbing, grounding on title
make test-automation        # stuck-goal job
make test-priority          # get_snapshot result, deletion of learning_context
make test-memory            # write_episode id, SurfacingGate removed
make test-core              # write_memory commit receives the episode ref
make test-messenger test-ingestion test-calendar
make test                   # ze-api: snapshot route, config shipped keys; pg tests SKIP without ZE_TEST_PG
make test-web typecheck-web
make lint

make test-pg                # needs Docker (or ZE_TEST_PG_URL): real migrations, real rows
make codegen                # after the schema change; commit the generated client
```

Without Docker: `make test-py` still passes; the pg tests show as skipped with the reason.

Manual check after the acceptance tests (read-only, optional): start `make dev`, open `/priority`, confirm goals appear and no "couldn't load" notice shows. Do not write to the dev database from scripts.
