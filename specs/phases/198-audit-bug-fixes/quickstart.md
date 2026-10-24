# Quickstart: Audit Bug Fixes

How to see each fix working. Run from the repo root of the floor checkout.

## Gates

```bash
make test-py          # every Python suite
make test-web         # ze-ui + ze-web vitest
make typecheck-web
make lint
make test-pg          # optional: real-Postgres tests touched by the PriorityView and LoopSurfacer wiring
```

## Per bug

| Bug | Test that failed before the fix | Manual check (`make dev-full`) |
|---|---|---|
| B1 | `make test-core` → `tests/orchestration/nodes/test_execution.py` (single and compound zone); `make test-agents` → `test_delegate.py`; `make test-automation` → `goal_engine/test_executor.py`; `make test` → `test_settings_timezone.py` | Set `TIMEZONE=Europe/Lisbon` in `apps/ze-api/.env`. Ask "what time is it?" and check the trace's prompt: the date line names Lisbon, not UTC. |
| B2 | `make test` → `test_container_config.py` | Say "I met Ana at the Lisbon office today". Mind › Find an entity finds "Ana" within a minute. |
| B4 | `make test-worldstate` → `test_surfacing.py`; `make test-priority` → `test_arbitration.py` end-to-end case | — (needs a drifting loop and an arbitration run; covered by the tests) |
| B5 | `make test-priority` → `test_view.py`, `test_tools.py`, `test_arbitration.py` | On World, drag a loop above a higher one. Ask "what's slipping?" and then "make <the moved loop> more urgent": Ze says it is already the most urgent. |
| B6 | `make test-core` → `tests/orchestration/test_compaction_readout.py` | Hard to reach by hand (needs 70% of the context window). Covered by the test. |
| B9 | `make test` → `api/test_workspace_followthrough.py` | Ask Ze to run a long workspace command that, when finished, writes a file that asks first. The confirmation card appears on the thread. |
| B10 | `make test-web` → `TurnFrameHandler.test.tsx`, `reducer.test.ts` | Start a turn that asks first, switch to another thread before the card appears: the first thread keeps its dot in the sessions rail. |
| B11 | `make test-personal` → `jobs/test_briefing.py`; `make test-automation` → `proactive_jobs/`, `workflow_engine/test_failure_handler.py`; `make test-calendar` → `jobs/test_reminders.py` | Point `NTFY_BASE_URL` at an unreachable host, trigger the morning brief, restore it, trigger again: the second run sends. |
| B13 | `make test` → `test_data_domains_unique.py` | Governance › Data lists goals and workflows once. |
| B14 | `make test-automation` → `goal_agent/test_goal_agent.py`, `goal_engine/test_lifecycle.py`; `make test` → `api/test_goal_actions.py` | Ask Ze to pause a completed goal: it refuses, and Retry has nothing to undo. |
| B15 | `make test-core` → `tests/conversation/test_turn_abort.py` | Ask a long research question, press Cancel: no reply arrives afterwards. |

`make test` runs the ze-api suite; the other targets are listed in `docs/testing.md`.
