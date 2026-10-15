# Quickstart: Loop Confirmation Path (171)

Prerequisites: 169 and 170 on `main` and merged into this branch; `make install web-install`; Docker for `make test-pg`.

```bash
# backend units
make test-worldstate test-priority test-agents test-core test lint
# real Postgres (170 harness): confirm stamps 0.9 + deadline; offer cooldown through push_log
make test-pg
# detector: offline set check, tuned sweep, then the one held-out verdict
make calibrate-open-query ARGS="--check-sets"
make calibrate-open-query
make calibrate-open-query ARGS="--set holdout --threshold <T>"
make test-priority SLOW=1          # held-out regression with the real E5
# web
make codegen && make test-web typecheck-web
```

Manual check (`make dev-full`):

1. Insert or produce a suspected loop (e.g. send yourself an email that implies a follow-up, or `UPDATE open_loops SET state='suspected', confidence=0.3 WHERE ...` on a dev row).
2. Open **Automation → Open loops**: the loop is under "Needs your OK". Press Keep: it moves to "Tracking"; `GET /api/v0/loops` shows confidence 0.9.
3. Make another suspected loop. Wait past `session_inactivity_minutes` (or lower it in config), then send any message. The reply ends with a question about it; the trace panel shows `loop_offer_ids`. Answer "yes, keep it": the loop is active.
4. Ask "O que tenho em aberto?": the reply lists ranked open items.
