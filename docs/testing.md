# Testing

All tests run from the **repository root**. Every package has a `make test-<name>` target;
`make test-all` runs the full suite across all packages.

---

## Quick reference

| Target | Package | Runner |
|---|---|---|
| `make test` / `make test-api` | ze-api | pytest |
| `make test-core` | ze-core | pytest |
| `make test-logging` | ze-logging | pytest |
| `make test-agents` | ze-agents | pytest |
| `make test-plugin` | ze-plugin | pytest |
| `make test-sdk` | ze-sdk | pytest |
| `make test-proactive` | ze-proactive | pytest |
| `make test-memory` | ze-memory | pytest |
| `make test-automation` | ze-automation | pytest |
| `make test-worldstate` | ze-worldstate | pytest |
| `make test-skills` | ze-skills | pytest |
| `make test-workspace` | ze-workspace | pytest |
| `make test-workspace-sidecar` | workspace sidecar | pytest |
| `make test-priority` | ze-priority | pytest |
| `make test-collision` | ze-collision | pytest |
| `make test-seed` | ze-seed | pytest |
| `make test-ingestion` | ze-ingestion | pytest |
| `make test-onboarding` | ze-onboarding | pytest |
| `make test-correlation` | ze-correlation | pytest |
| `make test-browser` | ze-browser | pytest |
| `make test-notifications` | ze-notifications | pytest |
| `make test-components` | ze-components | pytest |
| `make test-eval` | ze-eval | pytest |
| `make test-google` | ze-google | pytest |
| `make test-trading212` | ze-trading212 | pytest |
| `make test-yt` | ze-yt | pytest |
| `make test-communication` | ze-communication | pytest |
| `make test-personal` | ze-personal | pytest |
| `make test-messenger` | ze-messenger | pytest |
| `make test-calendar` | ze-calendar | pytest |
| `make test-prospecting` | ze-prospecting | pytest |
| `make test-news` | ze-news | pytest |
| `make test-finance` | ze-finance | pytest |
| `make test-web` / `make web-test` | @myguyze/ze-ui + ze-web | vitest |
| `make typecheck-web` | @myguyze/ze-ui + ze-web | tsc |
| `make test-py` | all Python packages | pytest |
| `make test-pg` | real-Postgres tests (Docker) | pytest |
| `make test-all` | all packages | pytest + vitest |

---

## Conventions

### Target naming

- Pattern: `make test-<short-name>` where `<short-name>` is the package name without the
  `ze-` prefix (`ze-personal` → `test-personal`, `ze-api` → `test-api`).
- `make test` is a shortcut for `make test-api` (the default CI gate).
- `make test-web` and `make web-test` are equivalent.

### Test layout

- Python packages: tests live in `<package>/tests/`, mirroring the package structure.
- React app: tests live in `apps/ze-web/src/**/*.test.ts(x)`.
- Run from the repo root — never `cd` into a package to run tests in CI or docs. The
  Makefile targets handle any `cd` themselves.

### Default pytest invocation

Every Python `test-*` target runs:

```bash
uv run pytest <package>/tests -m 'not slow' -q
```

Pass `SLOW=1` to include slow tests (embedding model load in ze-core):

```bash
make test-core SLOW=1
```

`make test-py` runs every Python package target. It keeps going when a suite fails, then
exits non-zero and names each failed target. CI runs `make test-py`, so a local run matches CI.

`make test-all` runs `make test-py` with `SLOW=1`, then `test-web`.

### Real-Postgres tests

Some regressions need a real Postgres. They live in `apps/ze-api/tests/pg/` and carry the
`pg` marker: the drift sweep, stuck-goal detection, loop evidence, and the two acceptance
runs.

`make test-pg` starts a throwaway `pgvector/pgvector:pg16` container, applies the
migrations, runs the `pg` tests, and removes the container. The container maps a random
host port, so it never touches the dev database on port 5432. Docker must be running;
without it the run exits with `PgHarnessError`.

The tests skip unless `ZE_TEST_PG=1`, which `make test-pg` sets. `make test`, `make
test-py`, and `make test-all` do not set it, so they collect and skip the `pg` tests and
never call Docker.

To run against an existing Postgres instead of a container, set `ZE_TEST_PG_URL` to its
`postgresql://` URL.

### Direct pytest (fallback)

When filtering to a single file or test name:

```bash
uv run pytest core/cognition/ze-memory/tests/test_store_writes.py -q
uv run pytest apps/ze-api/tests -k test_health -q
```

---

## What to run when

| Change location | Run |
|---|---|
| Any Python package | `make test-<name>` for that package |
| Multiple packages / unsure | `make test-py` (what CI runs) or `make test-all` |
| Before opening a PR | `make lint` and `make test-py`; `make typecheck-web` and `make test-web` if ze-web or @myguyze/ze-ui changed |
| Embedding / routing internals | `make test-core SLOW=1` or `make test-all` |

---

## Adding a new package

1. Create `<package>/tests/` with at least one test module.
2. Add a `test-<short-name>` target to the Makefile and add it to `TEST_PY_PACKAGES`. CI runs only the targets in that list.
3. Document the target in the package README `## Testing` section.
4. Add a row to the table in this file.
