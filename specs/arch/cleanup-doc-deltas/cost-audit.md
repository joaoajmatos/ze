# Cost audit doc deltas (for CF-16)

Floor notes are deleted on land. CF-16 applies these. Source: `specs/arch/cost-audit-2026-10.md`
and the fixes on branch `cost-audit`. No migration.

## AGENTS.md

### Section "Configuration files"

Before the `config.yaml` entry, add:

> ### `apps/ze-api/config/profiles/<name>.yaml`
> Optional overlay deep-merged over `config.yaml` when `ZE_PROFILE=<name>` is set. `make dev`,
> `dev-full` and `dev-eval` set `quiet` (no unattended LLM jobs, no boot-time catch-up); production
> never sets it. Every key in an overlay must exist in `config.yaml` (a test pins this).

### Section "Learned Workspace Facts"

Add:

> - Dev runs under `ZE_PROFILE=quiet` (`make dev ZE_PROFILE=` for the full config). The profile
>   also turns off memory consolidation and session summaries, because one flag gates both, so dev
>   and dev-eval memory has no consolidated or summarised episodes.

## docs/configuration.md

### Top of the file, after "All files live in `apps/ze-api/config/`…"

Add a "Config profiles" subsection:

> A profile is a YAML file in `config/profiles/` that overrides part of `config.yaml`. Set
> `ZE_PROFILE=<name>` to load it. Ze merges the profile over `config.yaml`: nested mappings merge,
> and lists and scalars replace. An unknown or malformed name stops startup with an error.
>
> `make dev`, `make dev-full`, and `make dev-eval` set `ZE_PROFILE=quiet`. The `quiet` profile
> turns off the work nobody watches while you develop:
>
> - It scores news with heuristics only (no model call per article) and fetches once a day.
> - It turns off the weekly insight and goal jobs, the nightly dream and memory consolidation
>   jobs, and session summaries. Contacts consolidation goes with memory consolidation.
> - It stops the correlation scan.
> - It stops a restart from running every job it missed.
>
> It leaves routing, skills, and commitment intake as shipped, so chat and evals behave the same,
> but dev and eval memory no longer consolidates or summarises sessions. Run
> `make dev ZE_PROFILE=` to use the full shipped config. Production never sets `ZE_PROFILE`.

### Section "`config/config.yaml`" (the proactive keys)

Document three keys under `proactive:`:

- `catch_up` (default `true`): `false` stops a restart from running any job it missed.
- `catch_up_max_age_hours`: maps a job id to the oldest missed run that still catches up. The
  shipped config limits `news_fetch`, `session_summary`, `goal_advance_sweep`, `inbound_poll`,
  `quiet_hours_release` to 1 hour and `correlation_scan`, `attention_arbitration_sweep` to 4 hours.
  A max age set at registration (the briefing) wins over this map.
- `goal_advance_sweep.enabled` and `.cron` (defaults `true`, `*/15 * * * *`).

## docs/scheduled-jobs.md

### Section "Goal advance sweep (every 15 minutes)"

Stale text: `**Module:** ze_automation/goals/executor.py · registered in ze_api/container.py` and
`**Cron:** */15 * * * *`.

Change to: registered by `register_goal_advance_sweep` in `ze_automation/bootstrap.py`; cron and
`enabled` come from `proactive.goal_advance_sweep`. Add: an idle goal costs three database queries
and no model call, because `advance` returns before the model when a milestone is held or the goal
is not `ACTIVE`.

### Section on catch-up after downtime (line starting "Ze runs on a laptop")

After "The `quiet_hours_release` job does not catch up." add:

> Two config keys control catch-up. `proactive.catch_up: false` turns it off for every job.
> `proactive.catch_up_max_age_hours` maps a job id to the oldest missed run that still catches up.
> A max age set at registration (the briefing) wins over this map.

### Cost reconciliation (wherever `cost_reconciliation` is described)

Change to: every 15 minutes the reconciler prices up to 100 unpriced rows, newest first, between 2
minutes and 3 days old. It retries a 404 (OpenRouter may not have indexed the generation yet) and
gives up on a generation after three misses in a row. It gives up at once on a 400 invalid id. A row
older than 3 days keeps `cost_usd` NULL, meaning unknown; estimate it from
`ze_core/telemetry/pricing.py`.

## docs/architecture.md and the memory docs

Wherever write_memory is described as running an event extractor and an entity extractor, change to
one `turn_extractor` request that returns both, skipped on a trivial turn (greeting or
acknowledgement). `extract_events`, `extract_entities`, `gather_event_proposals`, and
`gather_entity_proposals` no longer exist; the configurable keys `event_extractor` and
`entity_extractor` are now `turn_extractor`. Also: `specs/arch/memory-package-split.md` row for
`Event` names `gather_event_proposals`; replace with `gather_turn_proposals`.

## docs on telemetry / cost

Add: every LLM call logs a flow and an agent. A conversation turn logs flow `user_message`
(session = thread id); a cron job logs flow `proactive`, agent = job id, session `job:<job id>`;
eval and workflow flows keep their own. Steps inside a turn log agents `router`, `skills`,
`memory_write`, `synthesis`, `session_title`. `ze_core.telemetry.pricing` prices System One
(`typesafe/jev-`, $0.042 per million prompt tokens, completion free) by slug prefix.

## specs/arch/cost-audit-2026-10.md (corrections to the report)

Apply these as edits to the report text, not as an addendum:

- Section 1.2, correlation scan row, and headline finding 6: the scan is not log-only. It also
  persists hypotheses that `PriorityView` ranks, so the shipped config keeps it. The quiet profile
  sets `correlation.push.dry_run: false`, which makes the scan return before its LLM call
  (`push.py:111`).
- Section 3.2: System One generation ids (`gen-dec-...`) resolve through `GET /generation` with
  real costs, so they are not permanently unresolvable. One older id answers HTTP 400. The cost
  fits native prompt tokens x $0.042 per million, completion free (four samples).
- Section 3.2, "Unexplained": a `GET` on one of the 6 rows now answers 404 like the 44, and a
  recent generation resolves (`total_cost` 0.000235966, matching the audit's $0.000238 estimate), so
  the lookup works. The old `updated=6` is still unexplained; the reconciler now counts a row only
  when the `UPDATE` changed one and logs `cost_reconcile_update_changed_no_row` otherwise.
- Section 1.2, `goal_advance_sweep` row: it makes no model call for an idle goal. It lists only
  `ACTIVE` goals, and `advance` returns before the model when a milestone is held or the goal is
  not active. Tests pin both early returns.
- Section 5, win 8 (title only until it exists): the generated title replaces the 60-character
  placeholder the first message saves (`title_source` `user`) once, then `generated` stops it. There
  is no rename route, so `user` is only that placeholder. Nothing was overwriting a user title.
