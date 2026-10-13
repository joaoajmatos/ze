# Contract: real-Postgres harness

Location: `apps/ze-api/tests/pg/`. Nothing here is imported by production code.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | package marker |
| `conftest.py` | skip logic, session DSN fixture, per-test pool fixture, table reset |
| `_container.py` | start/stop helpers around the `docker` CLI |
| `test_harness_smoke.py` | the harness itself: migrations applied, `open_loops` and `goal_gates` exist, truncate works |
| `test_drift.py`, `test_stuck_goals.py`, `test_loop_evidence.py`, `test_acceptance.py` | the regression and acceptance tests |

## Skip rule

```python
def pytest_collection_modifyitems(config, items):
    if os.environ.get("ZE_TEST_PG") == "1":
        return
    skip = pytest.mark.skip(reason="set ZE_TEST_PG=1 (make test-pg) to run real-Postgres tests")
    for item in items:
        if "pg" in item.keywords:
            item.add_marker(skip)
```
`pytestmark = pytest.mark.pg` at the top of every file in the directory. Collection never touches Docker.

## Session fixture

```python
@pytest.fixture(scope="session")
def pg_dsn():                       # sync fixture, returns the asyncpg URL
    if os.environ.get("ZE_TEST_PG") != "1":
        pytest.skip("pg tests disabled")
    url = os.environ.get("ZE_TEST_PG_URL")
    handle = None
    if not url:
        handle = start_container()                  # raises PgHarnessError with one clear message
        url = handle.asyncpg_url
    migrate_url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    ze_api.migrate.upgrade(migrate_url)
    yield url
    if handle: handle.stop()
```

`start_container()`:
1. `docker info` must succeed, else `PgHarnessError("Docker is required for make test-pg (or set ZE_TEST_PG_URL)")`.
2. `docker run -d --rm -p 127.0.0.1::5432 -e POSTGRES_USER=ze -e POSTGRES_PASSWORD=ze -e POSTGRES_DB=ze pgvector/pgvector:pg16`.
3. `docker port <id> 5432` → host port.
4. Retry `docker exec <id> pg_isready -U ze` up to 30 s.
5. Register `atexit` stop as a second line of defense.

Container name is not fixed (no clash with `ze-postgres-1`). The image tag is a module constant.

## Function fixture

```python
@pytest.fixture
async def pg_pool(pg_dsn):
    pool = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=4)
    async with pool.acquire() as c:
        await c.execute("TRUNCATE " + ", ".join(RESET_TABLES) + " RESTART IDENTITY CASCADE")
    yield pool
    await pool.close()
```

`RESET_TABLES` is one explicit tuple: `open_loops, memory_relationships, memory_episodes, memory_facts, memory_entities, goals, goal_gates, goal_milestones, push_log, correlation_hypothesis, priority_overrides, notifications`. Adding a table is a visible edit.

## Builders (in `conftest.py` or `_builders.py`)

Small, explicit helpers so tests read as scenarios: `make_loop(pool, *, state, deadline, confirmed_at=...)`, `make_goal_with_gates(pool, ...)`, `make_episode(pool, agent, prompt, response)`. They use the real stores where a public create exists and raw `INSERT` where a test needs to backdate a timestamp. They never mock a store.

## Fakes allowed

Embedder, NLI client, relevance model, notifier, push log may be fakes. Stores and the database are real.

## Make target

```make
.PHONY: test-pg
test-pg:
	ZE_TEST_PG=1 uv run pytest -q -m pg apps/ze-api/tests/pg
```
Help line: `test-pg   Real-Postgres tests (needs Docker or ZE_TEST_PG_URL); not part of test-py`.

## Guarantees

- `make test`, `make test-api`, `make test-py`, `make test-all` collect the pg tests and skip them with the reason above. No Docker call.
- `make test-pg` without Docker exits non-zero with `PgHarnessError`.
- A failing test leaves no container: `--rm` plus session finalizer plus `atexit`.
- The dev database (`ze-postgres-1`, port 5432) is never used: the container maps a random host port.
