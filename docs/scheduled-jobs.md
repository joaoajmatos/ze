# Ze — Scheduled Jobs & Memory Lifecycle

Ze isn't only reactive. A set of background jobs run on a daily and weekly cadence
to keep memory clean, synthesize a portrait of the user, surface insights, and push
proactive messages — all without the user prompting anything.

This document explains what runs, when, and how each piece feeds into the next.

---

## The memory lifecycle

Every conversation leaves a record. Over time those records build into something
richer:

![Process diagram showing conversations producing facts and episodes, which feed a periodic session summary and nightly consolidation, then user profile synthesis, weekly insight generation, and the morning briefing](diagrams/docs/scheduled-jobs.svg)

<sub>[Interactive version](diagrams/docs/scheduled-jobs.html)</sub>

---

## What happens during a conversation

**Facts** (`ze_memory/extractor.py`)

After each `execute_tool` node, `write_memory` fires
(fire-and-forget). Explicit companion writes already landed via `remember_fact`.
The commitment intake then judges the turn (System One), and the Haiku extractor with its keep/drop + `speech_act` gate runs only as the fallback. Either path writes the remaining facts
through `submit_perception_facts` as `prompt_supplied`, `reviewed = false`. Eval threads
skip extraction. `POST /api/v0/memory/facts/review` exposes review/edit/reject.

**Episodes** (`ze_memory/retriever.py`)

Ze automatically writes a raw record of the conversation turn (prompt + response) as
an episode after every run. Episodes don't require user approval.

**Session summaries** (`ze_memory/session_summary.py`)

`SessionSummariser` runs every 10 minutes. When a session has been inactive for ≥ 30
minutes, Haiku generates a single narrative summary of the full session and writes it
to `memory_session_summaries`. If the user returns and adds more turns before the
session is archived, Ze regenerates the summary on the next tick. Raw episodes stay
until nightly archival removes them — at that point Ze skips the LLM call because
the eager summary already exists.

**Memory injection**

On the _next_ conversation, `fetch_context` retrieves facts (companion pins reviewed
facts always-on, then similarity-ranks the rest), raw episodes (current session only),
and session summaries (closed sessions). `_build_system_prompt` places constitution
and the agent job before that biography. Ze excludes sessions with a summary from the
raw episode query so the agent never sees both fragments and the narrative for the
same session. Ze also injects the user profile.

---

## Nightly consolidation (2 AM UTC)

**Module:** `ze_memory/consolidator.py`  
**Config:** `memory.consolidation.*` in `config/config.yaml` (optional overrides; defaults in `ze_memory/defaults.py`)

These tasks run in sequence every night:

### 1. Fact deduplication

Near-duplicate facts dilute retrieval precision and waste token budget. The
consolidator scans all unreviewed facts, computes pairwise cosine similarity, and
merges candidates above the configured thresholds:

![Graduated four-band ladder showing that fact pairs above 0.95 cosine similarity are silently merged with no LLM call, pairs between 0.85 and 0.95 go through NLI entailment then an LLM merge, pairs between 0.60 and 0.85 get an NLI contradiction check only, and pairs below 0.60 are skipped entirely with no NLI call.](diagrams/docs/dedup-threshold-ladder.svg)

<sub>[Interactive version](diagrams/docs/dedup-threshold-ladder.html)</sub>

<details>
<summary>Table</summary>

| Similarity | Action |
|---|---|
| ≥ 0.95 (`merge_silent_threshold`) | Silent merge — keep the fact with the higher confidence, mark the other `contradicted = true`. No LLM call. |
| 0.85–0.95 (`merge_llm_threshold`) | NLI contradiction ≥ `nli_contradiction_threshold` → mark the older fact `contradicted`. NLI entailment ≥ `nli_entailment_threshold` confirms a paraphrase → LLM merge (Haiku writes one value, Ze inserts it as a new fact and marks both inputs `contradicted = true`). Ze merges only when neither fact comes from a dream and both share provenance and claim kind. |
| 0.60–0.85 (`nli_lower_cosine_bound`) | NLI contradiction ≥ `nli_contradiction_threshold` → mark older `contradicted`. Otherwise skip. |
| < 0.60 | No action — skip NLI. |

</details>

**Reviewed facts are never auto-merged.** A reviewed fact represents an explicit
user decision; touching it automatically would violate that contract.

### 2. Fact expiry

Three rules applied per run:

| Rule | Condition | Action |
|---|---|---|
| Grace delete | `expires_at` is set and has elapsed | Hard-delete |
| Contradicted cleanup | `contradicted = true` and older than `contradicted_ttl_days` (default: 30d) | Hard-delete |
| Stale unreviewed | `reviewed = false` and no activity for `unreviewed_ttl_days` (default: 90d) | Soft-expire: set `expires_at = NOW() + expiry_grace_days` |

When `expires_at` passes, the grace-delete rule removes the fact. Ze never soft-expires a
reviewed fact.

### 3. Episode archival

Raw episodes accumulate quickly. Ze archives them in two steps.

First, session archival (`session_grouping_enabled`, default on). Ze groups episodes older
than `episode_archive_days` (default: 7d) by session. For each session with at least
`min_session_episodes` (default: 3) episodes, Ze replaces the raw episodes with one session
summary, up to `max_sessions_per_run` (default: 10) sessions per run. When the eager summary
from the session summariser already exists, Ze reuses it and makes no LLM call.

Second, batch archival. Episodes older than `episode_archive_days` that have no summary are
candidates. When at least `episode_min_archive_batch` (default: 10) candidates exist, Haiku
summarizes up to `episode_archive_batch` (default: 20) of them into a single archive row and
Ze deletes the originals. This keeps the episodes table lean without losing history.

### 4. Profile facet synthesis (end of every consolidation pass)

After dedup + expiry + archival, the consolidator calls `ProfileSynthesizer.update_profile()`
(`ze_memory/synthesizer.py`). Haiku reads the 100 most recently updated facts that are not
`contradicted` and the 20 most recent episode summaries. It returns a list of facets that Ze
upserts into `memory_profile_facets` by key.

Profile facets are key-value pairs with stability (`stable` | `dynamic` | `transient`) and
confidence scores. Ze injects the facets into the agents' system prompts (`ze_memory/policies.py`). Agents see the
synthesized portrait, not only individual facts.

Profile synthesis is skipped when there are no facts and no episode summaries.

---

## Dream job (3 AM UTC)

**Module:** `ze_memory/dream/job.py` (`DreamJob`, job id `dream_memory`)  
**Config:** `dream.*` in `config/config.yaml`

When `dream.enabled: true`, the job runs nightly (default cron `0 3 * * *`). It has three
stages, each under `dream.job_timeout_seconds` (default 1800). A failed stage stops the later
stages.

1. **Sleep pass** — no LLM calls. Refreshes replay scores, picks replay candidates, archives
   session episodes, deduplicates facts (the same routines as the nightly consolidation),
   decays the `retrieval_weight` of episodes that were not replayed recently (and archives
   them when the weight falls to the forgetting threshold), and detects schema and policy
   candidate clusters.
2. **Dream pass** — runs when an LLM client is available. Synthesizes artifacts from the
   candidates and stages them for review.
3. **Morning integration** — the promoter admits well-supported artifacts to memory.

After the stages, the job deletes `memory_retrieval_cache` rows older than 1 day (Phase 79
session-cached NLI rerank; see [memory.md](memory.md)) and writes a journal entry to
`memory_dream_journal`. The morning briefing reports that entry.
See [dreaming.md](dreaming.md) for the full wake/sleep/dream pipeline.

---

## Weekly insights (Sunday 7 AM UTC)

**Module:** `ze_personal/jobs/insights.py`  
**Config:** `proactive.insights.*` in `config/config.yaml`

Every Sunday Ze looks back over the past 7 days of facts and episodes and generates
1–3 short, conversational observations — things the user might not have consciously
noticed:

> *"I've noticed you've mentioned sleep problems four times this week — anything going on?"*
>
> *"Your last three research sessions all circled back to distributed systems. Looks like that's becoming a recurring thread."*
>
> *"You said you wanted to practice Portuguese more, but I haven't seen that come up in our conversations for a couple of weeks."*

Insight categories: `pattern` | `trend` | `goal` | `tension`.

The same category won't fire again within `category_cooldown_days` (default: 7d) to
avoid repetition. Ze sends each insight as a `discretionary` push (kind `insight`) via
`ProactiveNotifier` (WebSocket or ntfy) before the 8 AM morning briefing, so they feel
like a natural start to the week.

Insight generation is skipped if fewer than `min_evidence` (default: 3) facts +
episodes exist in the lookback window.

---

## Morning briefing (8 AM UTC daily)

**Module:** `ze_personal/jobs/briefing.py`  
**Config:** `proactive.briefing.*` and `news.personalization.*` in `config/config.yaml`

A daily digest, sent as the `accountability` push kind `morning_brief` via `ProactiveNotifier`. No LLM call — it's a templated summary of stats and headlines:

- **Unreviewed facts** — facts Ze proposed that you haven't confirmed or rejected yet.
  If the count is at or above `unreviewed_nudge_threshold` (default: 5), the briefing
  includes a direct nudge to review them.
- **Scheduled workflows** — the names of the enabled scheduled workflows.
- **Recent failures** — any workflow runs that failed in the past 24 hours.
- **Follow-up nudges** — stale relationships that `PriorityView` ranks as `relationship` items.
- **Dream summary** — when the latest dream journal entry promoted insights or left items for
  review.
- **Personalized headlines** — when the `ze-news` plugin is enabled, the briefing appends
  a news section. With enough user preferences (≥ `news.personalization.min_preferences`, default 2),
  Ze ranks articles by cosine similarity against a snapshot of the user's interest
  vector built from stored facts and active goal titles. The section splits into two
  clearly labeled buckets:

  ```
  📰 For you (based on your interests):
    • Article title (source)

  🔭 Outside your usual:
    • Article title (source)
  ```

  Ze ranks the discovery bucket (`explore_ratio`, default 20%) by recency, not by
  interest score, so the user always sees genuinely fresh off-profile content. Below
  the fact threshold, or when personalization is disabled, the section falls back to
  a plain recency-ordered list under `📰 Headlines:`.

The briefing is deduplicated — it will not fire if one was already sent within the past
20 hours. Only a briefing that was delivered or held (for example by quiet hours) counts.
If the push fails, Ze tries again on the next run.

---

## Calendar sync and reminders (7:45 AM UTC daily)

**Module:** `ze_calendar/jobs/calendar_reminder.py` (`CalendarReminderJob`)  
**Config:** `proactive.calendar.*` in `config/config.yaml`

Each morning `CalendarReminderService` syncs Google Calendar events up to
`sync_days_ahead` (default: 7) days ahead. For each event, Haiku assesses the
appropriate reminder interval (e.g. 15 minutes before a video call vs. 1 hour before
a flight). `WorkflowScheduler` creates one-shot `DateTrigger` jobs accordingly.

When a reminder fires, Ze sends the event title and time as a `requested` push (kind
`calendar_reminder`) via `ProactiveNotifier`. A reminder that came due while the server
was down fires on startup, marked late ("(late, was due HH:MM)"); future reminders are
re-registered as usual. A reminder whose push fails is marked unsent again, so Ze sends
it late at the next startup.

Calendar sync runs at 7:45 AM — before the 8 AM briefing — so Ze captures upcoming
events with same-day reminders.

---

## Workflow failure alerts (immediate)

**Module:** `ze_automation/bootstrap.py` (the failure handler) + `ze_proactive/notifier.py`

When a scheduled workflow step fails, Ze sends an `accountability` push (kind
`workflow_failure`) immediately — no waiting for the morning briefing. A
`workflow_failure_cooldown_hours` (default: 1h) prevents alert spam for
repeatedly-failing workflows. The cooldown is per workflow: the alert claims
`OncePer("workflow_failure_alert:<workflow id>")` for that window. The claim holds only
after Ze delivers or holds the alert. If the alert fails, the next failure alerts
again at once. The failure itself stays in the workflow's execution record.

---

## Goal advance sweep (every 15 minutes)

**Module:** `ze_automation/goals/executor.py` · registered in `ze_automation/bootstrap.py`'s `register_goal_advance_sweep()`, called from `ze_api/wiring/jobs.py`  
**Job id:** `goal_advance_sweep` · **Cron:** `*/15 * * * *` (configurable via `proactive.goal_advance_sweep.cron`)

For each goal with status `ACTIVE`, the sweep calls `GoalExecutor.advance(goal_id)`.
The advance loop either:

- Fires a **verification gate** (kind `goal_gate`, `accountability`, with Proceed / Stop /
  Redirect options), setting status to `AWAITING_GATE` until you respond, or
- Runs the next pending **milestone** via the normal agent registry, stores output and
  a learning, and sends a short progress line (kind `goal_milestone_done`,
  `accountability`, e.g. *"✅ Draft target list done (2/8)"*).

The sweep skips goals in `AWAITING_GATE`, `PAUSED`, `PLANNING`, `COMPLETED`, or
`ABANDONED`. It is lightweight — it returns early when there is no actionable next step.

Ze handles gate responses conversationally, not on the cron tick: approving
or redirecting calls `advance` again from the conversation handler.

See [docs/goals.md](goals.md) for the full goal engine documentation.

---

## Held write expiry (hourly)

**Module:** `ze_automation/jobs/held_write_expiry.py` · registered in `ze_automation/bootstrap.py`
**Job id:** `held_write_expiry` · **Cron:** `0 * * * *` (set `proactive.held_write_expiry.cron` to change it)

A held write is an irreversible call from an unattended run that nobody approved in advance.
Ze pushes a `write_approval_held` notification when it holds the call. The hold stays open
for 24 hours. This job finds holds past that time and resumes each one as a timeout. A timeout
counts as a deny: the call does not run, the step gets a declined result, and the run continues.

Set `proactive.held_write_expiry.enabled: false` to turn the job off. Holds then stay open
until someone answers them. The hold itself is described in
[workflows.md](workflows.md#irreversible-steps-in-unattended-runs).

---

## Weekly goal narrative (Sunday 6 PM UTC)

**Module:** `ze_automation/jobs/goal_narrative.py`  
**Cron:** `0 18 * * 0` (configurable via `proactive.goal_narrative.cron`)

For each active goal, Ze synthesizes a one-paragraph weekly update: what was completed this week, any pending gate, and what comes next. Ze sends it as an `accountability` push (kind `goal_narrative`). Skips goals that had no activity in the past 7 days. If the push fails, Ze tries again on the next run.

---

## Weekly goal suggestions (Sunday 7 PM UTC)

**Module:** `ze_automation/jobs/goal_suggestion.py`  
**Cron:** `0 19 * * 0` (configurable via `proactive.goal_suggestion.cron`)

Analyzes recent memory facts, episodes, and past goal retrospectives to propose one new multi-week goal. The titles of active goals go to the planner so that it does not duplicate them. Ze sends the suggestion as a `discretionary` push (kind `goal_suggestion`) with **Yes, create it** / **Dismiss** options. Accepted suggestions open a goal creation flow. The job skips a run when Ze saved a pending, accepted, or dismissed suggestion in the past 6 days. It also expires pending suggestions older than 30 days.

---

## Stuck goal detection (Tuesday 9 AM UTC)

**Module:** `ze_automation/jobs/stuck_goals.py`  
**Cron:** `0 9 * * 2` (configurable via `proactive.stuck_goals.cron`)

Checks all active goals for inactivity. The window is fixed in code at 7 days:

- **Milestone stuck**: an `ACTIVE` goal with no milestone progress for 7 days.
- **Gate stuck**: a goal in `AWAITING_GATE` that has waited 7 days at a gate. Ze
  counts the first open gate that has fired and ignores gates it has not reached, so
  each goal appears once.

Ze sends one `discretionary` push per run (kind `stuck_goal`) that lists every blocked goal (one row per goal, from its first fired open gate), with action buttons. An idle active goal offers **Redirect**, **Pause**, and **Abandon**. A goal at a gate offers **Approve**, **Redirect**, and **Stop**. `last_stuck_alert_at` on each goal prevents a repeat alert for 14 days, and Ze marks a goal alerted only when the push was delivered or held.

---

## Weekly accountability narrative (Monday 9 AM UTC)

**Module:** `ze_automation/jobs/accountability.py` (`AccountabilityJob`)  
**Cron:** `0 9 * * 1` (configurable via `proactive.accountability.schedule`)

A weekly plain-text summary of everything Ze did while you weren't watching:

```
Ze activity report (last 7 days)

💸 Cost: $0.42 across 38 runs
   • research: 19 runs, $0.1800
   • email: 12 runs, $0.1400
   • prospecting: 7 runs, $0.1000

🎯 Goals
   • Advanced: "Send 10 outreach emails"
   • Stalled: "Write technical blog post"

⚙️  Workflows: no failures

⚠️  Anomalies
   • prospecting spent $0.3100 on one run (5.0× baseline) on 2026-06-09
```

Data sourced from:

| Source | What it captures |
|---|---|
| `llm_cost_log` | Per-agent run counts, token totals, and costs |
| `goal_milestones` | Milestones completed this week; pending milestones idle > `stall_days` (default: 3) |
| Workflow runs | Workflow failures in the period (`list_failed_executions`) |
| `accountability_anomalies` | Cost outliers flagged by `CostAnomalyJob` |

Ze sends the narrative as an `accountability` push (kind `accountability_narrative`). The job is deduplicated with a 6-day window under key `weekly_accountability` — safe to retry without double-sending. No LLM call; the narrative is purely templated.

The same data is available on-demand via the `/status` WebSocket command (see [native-interface.md](native-interface.md)).

---

## Cost anomaly detection (every 6 hours)

**Module:** `ze_automation/jobs/cost_anomaly.py` (`CostAnomalyJob`)  
**Cron:** `0 */6 * * *` (configurable via `proactive.accountability.cost_anomaly_schedule`)

Silently scans recent LLM runs and alerts if any single run cost significantly more than that agent's historical baseline:

- **Baseline**: median cost-per-run over the past 30 days. Uses median (not mean) to resist distortion from the very anomalies this check aims to detect.
- **Minimum samples**: the job requires at least `anomaly_min_samples` (default: 5) historical runs before an agent can have a baseline. It silently skips new agents.
- **Threshold**: `anomaly_threshold` × baseline (default: 4.0×). A run at 4.01× fires an alert; one at 3.99× does not.
- **Deduplication**: the job skips session IDs already logged in `accountability_anomalies` within the past 24 hours, so a single run never fires twice.

Ze sends the alert as an `accountability` push (kind `cost_anomaly`, urgency `high`), so it is never budgeted, but the governor holds it during quiet hours.

Alert format (ntfy, urgency `high`):

```
⚠️ Ze cost anomaly detected

The prospecting agent spent $0.31 on one run — 5.0× its usual $0.06.
Date: 2026-06-09
```

Ze writes anomaly records to the `accountability_anomalies` table and prunes them automatically after `anomaly_retention_days` (default: 30 days).

The threshold is a conservative first guess — calibrate after 30 days of live data.

---

## Checkpoint pruning (hourly)

**Module:** `ze_core/orchestration/checkpoint_pruner.py` (`CheckpointPruner`) · registered in `ze_core/bootstrap.py`  
**Job id:** `checkpoint_pruning` · **Cron:** `0 * * * *`

LangGraph's `AsyncPostgresSaver` writes a full checkpoint on every node transition and
never prunes old ones on its own — resume/replay only ever reads the latest checkpoint
per thread, so history beyond a small safety margin is pure storage growth. For each
`(thread_id, checkpoint_ns)`, keeps the most recent `keep_per_thread` checkpoints
(default 3) and deletes older rows from `checkpoints` + their `checkpoint_writes`, plus
any `checkpoint_blobs` no longer referenced by a kept checkpoint's `channel_versions`.

This only reclaims *logical* rows — Postgres `VACUUM` (run automatically by autovacuum)
adds the freed pages to the free-space map for reuse but doesn't shrink the file on
disk. The `pg_total_relation_size` figure shown on the Data Overview page (`graph.checkpoints`
domain) will plateau rather than keep climbing once this job is running continuously,
but a one-time backlog won't visibly shrink there without a manual `VACUUM FULL` /
`pg_repack` (not scheduled — it takes an exclusive table lock).

---

## Cost reconciliation (every 15 minutes)

**Module:** `ze_core/telemetry/reconciler.py` (`CostReconciler`) · registered in `ze_core/bootstrap.py`'s `register_engine_jobs()`, called from `ze_api/wiring/jobs.py`  
**Job id:** `cost_reconciliation` · **Cron:** `*/15 * * * *`

Pulls actual billed costs from the OpenRouter API and reconciles them against
estimated records in `llm_cost_log`. Runs frequently to keep cost data fresh.

---

## Stale campaign recovery (every 15 minutes)

**Module:** `ze_prospecting/jobs/campaigns.py` (`recover_stale_campaigns`) · registered via `ProspectingPlugin.register_proactive_jobs()`  
**Job id:** `recover_stale_campaigns` · **Cron:** `*/15 * * * *`

Marks prospecting campaigns that have been running longer than
`PROSPECTING_STALE_TIMEOUT_MINUTES` (or `prospecting.stale_timeout_minutes` in `config.yaml`; default: 10 min) as failed, preventing stuck
campaigns from blocking new runs.

---

## News fetch (every 30 minutes)

**Module:** `ze_news/jobs/fetch.py`  
**Config:** `news.fetch_schedule` in `config/config.yaml`

When the `ze-news` plugin is loaded, a fetch job runs on a configurable cron (default
`*/30 * * * *`). For each enabled source in `news.sources`, it fetches the RSS feed,
embeds each new article title + summary using the shared
`intfloat/multilingual-e5-base` model, and upserts into the `news_articles`
table. It skips duplicate URLs and prunes old articles after `news.retention_days`
(default: 7 days).

Each source is tagged at configuration time (e.g. `global`, `local`, `tech`, `pt`). The
`get_headlines` tool and the morning briefing use these tags for filtering.

---

## Open-loop upkeep (4 AM and 5 AM UTC)

**Modules:** `ze_worldstate/jobs/stale_suspicion.py`, `ze_worldstate/jobs/drift_sweep.py`
**Config:** `worldstate.stale_suspicion.*` and `worldstate.drift.*` in `config/config.yaml`

`StaleSuspicionJob` (default `0 4 * * *`) expires `suspected` loops that no new
evidence has confirmed within the window. `DriftSweepJob` (default `0 5 * * *`) moves
`active` loops to `drifting` when their drift deadline passes. New evidence on an
`active` loop pushes the deadline to at least 7 days from now; the drift window is a
code constant, not config. A loop that the user revives with `track_loop` gets a fresh window. See
[cognitive-architecture.md](cognitive-architecture.md).

---

## Hypothesis decay (3 AM UTC)

**Module:** `ze_correlation/jobs/hypothesis_decay.py` (`HypothesisDecayJob`)

The job lowers the confidence of correlation hypotheses that have gone without new
evidence. Set `correlation.hypothesis_decay.schedule` to change the default
`0 3 * * *`.

---

## Attention arbitration (every 4 hours)

**Module:** `ze_priority/arbitration.py` (`AttentionArbitrationJob`)
**Config:** `proactive.attention_arbitration.*`, `worldstate.push.*`, `correlation.push.*`

One job replaces the old per-source push sweeps. Each source describes its candidates
(`PushCandidate`), and one push bar (`ze_priority/push_bar.py`) screens them all. The bar
checks confidence, relevance, inline mentions in the conversation, novelty against recent
discretionary pushes, and grounding in evidence. The job drops a candidate whose
`OncePer` is cooling before the bar runs. It ranks the survivors with `PriorityView` and
sends the first one in rank order. It sends one push per run: it stops at the first push
that is sent or held, or that the budget suppresses. A candidate that fails with another
outcome passes to the next.

The job returns at once when the shared budget has no room left. Loop pushes (kind
`loop_drift`) require `worldstate.push.enabled: true`. A drifting loop is pushed at most
once per `worldstate.push.repush_after_days` (default 7). Hypothesis pushes (kind
`hypothesis`) require `correlation.push.enabled: true`, and `correlation.push.dry_run:
false` sends them; in dry run the job logs each candidate and sends nothing. A hypothesis
is pushed once ever (`OncePer("hypothesis:<id>")` with no window). Both kinds are
`discretionary`. The job never claims or releases the budget itself; the governor does.
See [cognitive-architecture.md](cognitive-architecture.md).

---

## Other scheduled jobs

| Job id | Default cron | What it does | Config |
|---|---|---|---|
| `correlation_scan` | `0 */4 * * *` | Forms correlation hypotheses from recent signals (`ze_correlation/job.py`). Attention arbitration pushes them. | `correlation.push.schedule` |
| `prune_notifications` | `0 4 * * *` | Deletes read notifications older than 90 days (`ze_proactive/jobs/prune_notifications.py`). | `proactive.notifications.prune_cron`, `.retention_days` |
| `inbound_poll` | every 5 minutes | Polls the registered inbound channels for new messages (`ze_messenger/jobs/inbound_poll.py`). | `proactive.inbound_poll_interval_seconds` (whole minutes, minimum 1) |
| `gmail_watch_renewal` | `0 0 * * 0` | Renews the Gmail push watch before it expires. Runs only when the Gmail channel supports push and `gmail_pubsub_topic` is set. | none |
| `finance.daily_snapshot` | `0 8 * * *` | Syncs positions and transactions from every configured finance data source. | `finance.snapshot_schedule` |
| `finance.recurring_detection` | `0 9 1 * *` | Detects recurring expenses. Off unless `finance.recurring_detection_enabled` is `true`. | `finance.recurring_detection_schedule` |

---

## Interruption governor

Every proactive push declares a `PushKind`: an event type plus a class, an urgency, and a source. One rule set in `ze_proactive/governor.py` decides what happens to each push.

| Class | Budgeted? | Quiet hours? |
|---|---|---|
| `requested` | No | Always delivered |
| `accountability` | No | Held |
| `discretionary` | Yes | Held |

Kinds by class:

| Class | Kinds |
|---|---|
| `requested` | `user_reminder`, `calendar_reminder`, `write_approval_held` |
| `accountability` | `confirmation_request`, `confirmation_timeout`, `workspace_run_completed`, `workflow_failure`, `goal_plan_proposed`, `goal_attention_needed`, `goal_plan_adapted`, `goal_milestone_done`, `goal_completed`, `goal_gate`, `cost_anomaly`, `accountability_narrative`, `goal_narrative`, `morning_brief`, `calendar_reminders_scheduled`, `quiet_hours_summary` |
| `discretionary` | `loop_drift`, `hypothesis`, `stuck_goal`, `goal_suggestion`, `goal_overlap`, `goal_reuse`, `insight`, `contact_review`, `finance_stale_nudge`, `finance_recurring_new`, `finance_price_change`, `inbound_message` |

`proactive.budget.max_pushes_per_day` (default 5) is one shared budget for every discretionary push. It counts claims in a rolling 24-hour window. `GET /api/v0/notifications/budget` reports the count and when the next slot opens, and `GET /api/v0/proactive/job-runs` lists the last run of each job. Accountability and requested pushes never claim it. A discretionary push must pass a `once_per` (`OncePer`) key. A key still inside its window returns `deduped` and sends nothing. The claim store is private to `ze-proactive` (table `push_log`, migration `zpro006`); other packages read the budget and the cooldowns through the notifier.

### Quiet hours and release

Quiet hours hold accountability and discretionary pushes. Ze records a held push in the bell with delivery `held`, sends no chat message and no ntfy, and releases it when quiet hours end. A requested push always buzzes, even during quiet hours. The budget check runs before the quiet hold. A discretionary push with no budget left is suppressed even during quiet hours, so the daily cap holds.

The user sets quiet hours in the Attention module of Governance (`/governance`). The window is stored in the `interruption_settings` table and evaluated in its own IANA zone. Quiet hours ship off. When the window ends, `QuietHoursReleaseJob` (`job_id = "quiet_hours_release"`, cron `proactive.notifications.release_cron`, default `*/5 * * * *`) delivers each held push in urgency order without a buzz, then sends one `quiet_hours_summary` push that buzzes once. A run with no held pushes does nothing.

### Catch-up for missed runs

Ze runs on a laptop, so a scheduled time can pass while the host is asleep. `ProactiveScheduler` records each run in `proactive_job_runs`. On startup, it runs a catch-up job once when the scheduled time passed since the last recorded run, within the job's `catch_up_max_age_hours`. The morning briefing sets this from `proactive.briefing.catch_up_max_age_hours` (default 6). A job with no recorded run does not run at startup. APScheduler `misfire_grace_time=None` with `coalesce=True` covers a process that was suspended over a fire time. The `quiet_hours_release` job does not catch up.

---

## Skill source recheck (6 AM UTC)

**Module:** `ze_skills/jobs/recheck.py`  
**Config:** `skills.recheck` in `config/config.yaml`

`SkillRecheckJob` re-fetches every imported skill's origin URL. Unchanged content
stays active. Changed content reverts to pending review and clears executable
approval. An unreachable source sets `last_check_error` and leaves the last
approved version in place.

See [skills.md](skills.md#daily-recheck).

---

## Full schedule at a glance

The pipeline diagram at the top of this document shows how conversations flow into
the morning briefing; the board below shows every scheduled job, grouped by cadence
tier instead of literal clock position.

![Board diagram grouping every scheduled job into four cadence tiers — fixed daily UTC times from 2 AM consolidation through 8:30 AM contact review, fixed weekly times from Sunday morning insights through Tuesday stuck-goal detection, continuous fixed-interval jobs from every 10 minutes to every 6 hours, and event-driven jobs that fire immediately on failure or trigger — with the weekly accountability narrative and cost anomaly detection called out as the two most consequential jobs.](diagrams/docs/job-cadence-board.svg)

<sub>[Interactive version](diagrams/docs/job-cadence-board.html)</sub>

<details>
<summary>Table</summary>

| Time (UTC) | Job | Module |
|---|---|---|
| 2:00 AM daily | Memory consolidation + profile synthesis | `ze_memory/consolidator.py` |
| 3:00 AM daily | Dream sleep pass + retrieval-cache expiry | `ze_memory/dream/job.py` |
| 3:00 AM daily | Hypothesis confidence decay | `ze_correlation/jobs/hypothesis_decay.py` |
| 4:00 AM daily | Stale open-loop suspicion expiry | `ze_worldstate/jobs/stale_suspicion.py` |
| 5:00 AM daily | Open-loop drift sweep | `ze_worldstate/jobs/drift_sweep.py` |
| 3:00 AM daily | Contacts consolidation (dedup + merge) | `ze_personal/contacts/consolidator.py` |
| 6:00 AM daily | Imported skill source-content recheck | `ze_skills/jobs/recheck.py` |
| Every 10 min | Session summary generation | `ze_memory/session_summary.py` |
| 7:00 AM Sun | Weekly insight generation | `ze_personal/jobs/insights.py` |
| 7:45 AM daily | Calendar sync + reminder scheduling | `ze_calendar/jobs/calendar_reminder.py` |
| 8:00 AM daily | Morning briefing (with personalized headlines) | `ze_personal/jobs/briefing.py` |
| 8:30 AM daily | Contact review suggestions | `ze_personal/jobs/contacts.py` |
| 6:00 PM Sun | Weekly goal narrative | `ze_automation/jobs/goal_narrative.py` |
| 7:00 PM Sun | Weekly goal suggestions | `ze_automation/jobs/goal_suggestion.py` |
| 9:00 AM Mon | **Weekly accountability narrative** | `ze_automation/jobs/accountability.py` |
| 9:00 AM Tue | Stuck goal detection | `ze_automation/jobs/stuck_goals.py` |
| Every 4 hours | Attention arbitration — ranked discretionary pushes through the governor | `ze_priority/arbitration.py` |
| Every 5 min | Quiet-hours release sweep | `ze_proactive/jobs/release_held.py` |
| Every 6 hours | **Cost anomaly detection** | `ze_automation/jobs/cost_anomaly.py` |
| Every 15 min | Goal advance sweep | `ze_automation/goals/executor.py` |
| Hourly | Held write expiry | `ze_automation/jobs/held_write_expiry.py` |
| Hourly | Checkpoint pruning | `ze_core/orchestration/checkpoint_pruner.py` |
| Every 15 min | Cost reconciliation | `ze_core/telemetry/reconciler.py` |
| Every 15 min | Stale campaign recovery | `ze_prospecting/jobs/campaigns.py` |
| Every 30 min | News article fetch + embed | `ze_news/jobs/fetch.py` |
| Immediate | Workflow failure alerts | `ze_proactive/notifier.py` |
| Immediate | Calendar event reminders (when they fire) | `ze_calendar/jobs/calendar_reminder.py` |
| Immediate | Goal verification gates + milestone progress | `ze_proactive/notifier.py` |

</details>

All scheduled jobs use APScheduler (via `WorkflowScheduler` or `ProactiveScheduler`).
Cron expressions are configurable in `config/config.yaml`. Jobs registered with
`ProactiveScheduler` catch up once after downtime (see
[Interruption governor](#interruption-governor)).

---

## Inspecting memory

| Endpoint | Description |
|---|---|
| `GET /api/v0/memory/feed` | Facts and episodes, newest first (with review status) |
| `GET /api/v0/memory/activity` | Per-day counts of facts and episodes between two dates |
| `POST /api/v0/memory/facts/review` | Confirm, reject, or edit a proposed fact |

---

## Adjusting the schedule

All cron expressions and thresholds live in `config/config.yaml` under `memory.consolidation`,
`dream`, `worldstate`, `correlation`, `skills`, `finance`, `news`, and `proactive`. See
[docs/configuration.md](configuration.md) for the full reference.
