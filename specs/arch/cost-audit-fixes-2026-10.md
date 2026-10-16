# Cost audit fixes, 2026-10

Follows `cost-audit-2026-10.md`. No migration: every fix below works on the existing schema.

## What changed

| Group | Change | Where |
|---|---|---|
| 1 | `NewsStore.upsert` detects a new article with `RETURNING (xmax = 0)`, not the command tag | `ze_news/store.py` |
| 1 | Cost context for turns (`enter_turn_context`), cron jobs (`ProactiveScheduler(job_context=...)`), and the `memory_write`, `skills`, `session_title` steps; `set_agent_context` no longer drops the agent when no flow is set | `ze_core/telemetry/context.py`, `turn.py`, `container.py`, `ze_api/compose.py` |
| 1 | Reconciler: newest first, 3-day window, batch of 100, remembers ids OpenRouter has no record of, counts only real updates | `telemetry/postgres.py`, `reconciler.py`, `openrouter/client.py` |
| 1 | System One priced: `typesafe/jev-` prefix, $0.042 per million prompt tokens, completion free | `telemetry/pricing.py` |
| 2 | One Haiku request returns a turn's events and entities (was two), and a trivial turn makes none | `ze_memory/extractor.py` (`gather_turn_proposals`), `nodes/memory.py` |
| 2 | Title generation skips any session that already has a title | `ze_api/api/websocket/session_titles.py` |
| 2 | Correlation scan: see "Decision" below | none |
| 3 | `ZE_PROFILE` overlay (`config/profiles/quiet.yaml`), set by `make dev`, `dev-full`, `dev-eval` | `ze_api/settings.py`, `Makefile` |
| 3 | `proactive.catch_up` global switch and `proactive.catch_up_max_age_hours` per job | `ze_proactive/scheduler.py`, `config.yaml` |
| 4 | `goal_advance_sweep` cron and `enabled` come from `proactive.goal_advance_sweep` | `ze_automation/bootstrap.py` |

## Decisions

**Correlation in dry-run.** The scan forms hypotheses that `PriorityView` ranks, so skipping its LLM
in production would remove a surface, not a log line. No code change. The `quiet` profile sets
`correlation.push.dry_run: false`; with `enabled: false` the scan returns before its model call. A
deployment that wants the same sets that one key.

**Reconciler without a migration.** A per-row attempt counter needs a column. The recency window
(3 days), newest-first order, and a process-local set of ids OpenRouter has no record of give the
same result: a row with no record costs one request per process start, then none, and ages out of
the window. Rows older than the window keep `cost_usd` NULL, which means "unknown". Estimate them from
`pricing.py` when a number is needed. If a persistent flag is wanted later, it is one nullable column
on `llm_cost_log` in the `zc` chain.

**Hard cut of the old extractors.** `extract_events`, `extract_entities`, `gather_event_proposals`
and `gather_entity_proposals` are deleted, with the `event_extractor` and `entity_extractor`
configurable keys. Pre-v1 rule: no shim.

**Catch-up limits shipped.** Jobs that run every few minutes or hours (`news_fetch`,
`session_summary`, `goal_advance_sweep`, `inbound_poll`, `quiet_hours_release`: 1 hour;
`correlation_scan`, `attention_arbitration`: 4 hours) skip a catch-up older than their limit. The
next tick is soon enough. Daily and weekly jobs still catch up.

## Not done

- The extraction call is still awaited inside `write_memory`. Moving it off the reply path is a
  separate change with its own failure modes.
- The audit's ranked win 7 (skip the routing Choice when E5 is decisive) needs a calibration pass.
