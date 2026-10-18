# Quickstart: Accountability Surfaces (B4)

## Automated
- `make test-memory`, `make test-worldstate`, `make test-personal`, `make test-messenger`, `make test` (routes), `make test-onboarding`.
- `make test-pg` for the two SQL filters (ledger subject, loops since).
- `make test-py`, `make lint`, `make test-web` (codegen consumers).

## Manual against `make dev` (seeded)
1. `GET /api/v0/actions?subject_type=goal&subject_id=<seed goal>` → only that goal's actions, newest first; follow `next_cursor`.
2. `GET /api/v0/collisions` on the product API → entries; `GET` on the old dev path → 404.
3. `GET /api/v0/system/models` → complexity on, 0.40; set `simple_max` off in config, SIGHUP, read again → off.
4. `GET /api/v0/loops?state=closed&since=<7 days ago>` → only recent closures.
5. `GET /api/v0/channels/status` → seeded channel states; revoke a dev Google token, wait one poll → `needs_reauth`.
6. `make reset-personal-state` → no such target; `make db-reset-seed` still works.
