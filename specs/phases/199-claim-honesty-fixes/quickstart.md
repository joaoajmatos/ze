# Quickstart: verifying 199

Prerequisites: `make install`, Docker running (or `ZE_TEST_PG_URL`).

## 1. Unit suites

```bash
make test-plugin        # Executive licence (ze-plugin)
make test-memory        # dream promoter
make test-core          # write_memory provenance
make test-ingestion     # sink provenance
make test-messenger     # inbound fact provenance
make test-worldstate    # derived claim kind, resolve, fakes
make test-priority      # constructors updated; no source change
make test-personal      # contact provenance, co-occurrence origin
make test-prospecting   # research source is live_search
make test-seed          # seed facts no longer synthesized
make test               # ze-api (loops route nullable claim_kind)
make lint
```

(The exact target names are in `docs/testing.md`. Use `make test-py` for all of them.)

## 2. Real Postgres

```bash
make test-pg
```

Expected new tests to pass in `apps/ze-api/tests/pg/`:

- `test_dream_decay_pg.py`: a perception fact aged 60 days is unchanged after 10 integration runs. A dream insight decays 0.03 a run and expires past `valid_until`. A night with a promotion still decays.
- `test_zm026_pg.py`: the re-stamp changes only `synthesized` facts with no dream run, reports the decay-damaged count, and changes 0 rows on a second run.
- `test_loop_claim_kind_pg.py`: suspected reads suspicion; confirm, promote, drift and close read priority; dropped reads none; the column is gone.
- `test_loop_resolve_pg.py`: a resolve closes suspected, active and drifting loops for conversation, email and ingestion, and links the evidence. `transition(CLOSED)` from suspected is still refused. There is no fingerprint and no `loop_extraction_failed`.
- `test_contact_provenance_pg.py`: consolidator writes `prompt_supplied`; prospecting writes `live_search`; zc041 re-stamps and is idempotent.

## 3. Web and client

```bash
make codegen
make typecheck-web
make test-web
```

`LoopListItem.claim_kind` is `string | null`, and the three web readers type-check.

## 4. Migration on the dev DB

```bash
make migrate
make logs   # look for zm026_restamped restamped=2 decay_damaged=0 on the local ze DB
```

Then check the database:

- `\d open_loops` shows no `claim_kind`.
- `SELECT count(*) FROM memory_facts WHERE provenance='synthesized' AND dream_run_id IS NULL` returns 0.
