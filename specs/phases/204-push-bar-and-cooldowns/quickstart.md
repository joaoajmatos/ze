# Quickstart: verify Push Bar and Cooldowns

Run from the floor root. Contracts: [contracts/](contracts/). Data: [data-model.md](data-model.md).

## Prerequisites

- `make install`
- Docker running, or `ZE_TEST_PG_URL` set, for `make test-pg`. Never point tests at the shared `ze` database.

## 1. Unit suites per package

```bash
make test-proactive        # OncePer, is_sent, claim rules, notify outcomes (US1)
make test-priority         # PushBar.screen, arbitration, TurnSurfacing memory (US2, US4, US5)
make test-worldstate       # LoopSurfacer as a candidate source
make test-correlation      # CorrelationPushCandidateSource as a candidate source
make test-automation       # cooldown jobs, failure handler, list_failed_executions readers (US1, US3)
make test-personal test-calendar test-finance test-messenger test-sdk
make test                  # ze-api wiring, governor acceptance, shipped config keys
```

Expected: all green.

Key tests and what they prove:

| Test | Proves |
|---|---|
| `ze-proactive/tests/test_notifier_once_per.py` (parametrized over `failed`, `suppressed_budget`, `held`, `delivered`) | SC-002: only `delivered`/`held` start a cooldown; `deduped` inside the window |
| `apps/ze-api/tests/test_cooldown_jobs.py` (parametrized over the four FR-007 jobs, real notifier, failing then working interface) | US1 scenarios 1-4 |
| `ze-priority/tests/test_arbitration.py::test_bar_rejects_ungrounded_and_repeated_loop` | SC-003, US2 scenarios 1-2, through `AttentionArbitrationJob.run` only |
| `ze-priority/tests/test_arbitration.py::test_loop_and_hypothesis_share_history` | US2 scenario 3 |
| `ze-priority/tests/test_push_bar.py::test_grounding_off_logs_once` | US2 scenario 4, FR-004 |
| `ze-priority/tests/test_arbitration.py::test_inline_mention_blocks_push` | US4 scenario 1 |
| `ze-priority/tests/test_arbitration.py::test_loop_repush_after_window` | US5, SC-006 |
| `ze-automation/tests/.../test_status_lists_unpushed_failures` | US3, SC-004 |

## 2. Real Postgres

```bash
make test-pg
```

Expected: `test_push_claims_pg.py` (claim rules, concurrent claim, `zpro006` upgrade), `test_loop_confirmation_pg.py` (offers cool for a week on `surfacing_memory`), `test_workflow_failures_pg.py` (`list_failed_executions`), and `test_acceptance.py` (a drifting loop reaches arbitration) pass.

## 3. Grep gates

```bash
# SC-001: nothing outside ze-proactive names the push log (expect no output)
rtk proxy grep -rn 'push_log\|PushLogStore' core plugins apps packages integrations --include='*.py' \
  | grep -v '/tests/' | grep -v '/migrations/' | grep -v '^core/contracts/ze-proactive/'

# FR-013 / FR-014: the deleted names and the hand-rolled check are gone (expect no output)
rtk proxy grep -rn 'budget_key\|dedup_hours\|exists_recent\|was_sent_within_hours\|list_recent_payloads\|passes_novelty\|passes_grounding\|list_recently_surfaced_summaries\|in ("delivered", "held")' \
  core plugins apps packages --include='*.py' | grep -v '/tests/' | grep -v 'ze_proactive/types.py'
```

`is_sent` in `ze_proactive/types.py` is the one definition of the `delivered`/`held` check, so that file is excluded.

## 4. Migrations

```bash
make db-up && make migrate     # on a throwaway database, e.g. DATABASE_URL pointing at ze_e2e_204
```

Expected: `zpro006` and `zpri002` apply; `\d push_log` shows `claim_key`, `discretionary` and the two new indexes; `\d surfacing_memory` exists.

## 5. Lint and docs

```bash
make lint
git diff main...HEAD --stat -- docs README.md AGENTS.md '*/README.md'
```

Expected: lint clean; every doc listed in the plan's DOCS tasks appears in the diff.
