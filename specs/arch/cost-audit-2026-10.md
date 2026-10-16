# LLM cost audit, 2026-10

Status: report only. No behavior changed. The user picks the fixes (section 5).

Method: code read on branch `cost-audit` (main merged 2026-10-16), read-only SQL on the shared dev DB
(`ze`, table `llm_cost_log`), and the dev server log (`apps/ze-api/logs/ze.log`, to 2026-10-12).
No live model calls were made. One session-local temp table in the `postgres` database checked a
Postgres command tag (section 3.3); nothing persisted.

How to read the numbers: **Verified** = seen in code and in DB or log. **Inferred** = follows from
the code, not seen in data. Dollar figures use the static table in
`ze_core/telemetry/pricing.py` (Haiku 4.5 $1/$5, Sonnet 4.5 $3/$15, gpt-4o-mini $0.15/$0.60 per
million tokens) because the DB holds no real costs (section 3.2).

## Headline findings

1. **News re-scores the whole feed on every fetch.** `NewsStore.upsert` decides "new article" with
   `status == "INSERT 0 1"`, but `INSERT ... ON CONFLICT DO UPDATE` returns `INSERT 0 1` for an
   update too. Every re-fetched article is treated as new, so each fetch sends about 95 articles to
   gpt-4o-mini (verified). This is the whole `gpt-4o-mini unknown/unknown` volume.
2. **93.5% of all rows log as `unknown/unknown`.** Nothing sets the cost context on WebSocket turns
   or cron jobs, and `set_agent_context` does nothing when no context exists.
3. **`cost_usd` has been NULL since 2026-06-26.** The reconciler picks the 50 oldest unpriced rows
   each run. 44 of them can never resolve (OpenRouter answers "not found"), so the batch never
   reaches newer rows. 18,184 rows are pending.
4. **Two Haiku calls run on every conversation turn** (event and entity extraction), awaited inline
   in `write_memory`, with no trivial-turn gate.
5. **Every missed cron job fires at boot.** `catch_up=True` is the default and only the briefing
   sets a max age. Under `make dev`, a restart after a gap re-runs news, consolidation, dream and
   the rest.
6. **The correlation scan runs its LLM in dry-run.** Shipped config has `push.enabled: false` and
   `dry_run: true`, and the code only returns early when both are false.

Observed spend is small in dollars (about $1.44 in the last 7 days at table prices; about $4.2 of
gpt-4o-mini since June). The cost is call volume, noise in the telemetry, and the inability to
attribute any of it.

## 1. Unattended callers

Frequencies assume the server is up 24 hours. `make dev` is not, so observed numbers are lower.

### 1.1 Observed in `llm_cost_log` (last 7 days)

Only 3 days had traffic (Oct 12, 13, 15). Totals: 1,156 rows, 1.4M tokens, 0 with `cost_usd`.

| model | agent / flow | calls | prompt tok | completion tok |
|---|---|---|---|---|
| openai/gpt-4o-mini | unknown / unknown | 904 | 528,904 | 225,578 |
| typesafe/jev-1.13 (System One) | unknown / unknown | 36 | 43,716 | 4,371 |
| anthropic/claude-haiku-4-5 | unknown / unknown | 26 | 40,807 | 1,634 |
| anthropic/claude-sonnet-4-5 | unknown / unknown | 16 | 63,662 | 1,079 |
| (all others) | eval, workflow_execution | 174 | | |

The 904 gpt-4o-mini calls come in bursts, not at a steady cadence. Per hour: Oct 13 19:00 = 186,
20:00 = 200, 21:00 = 20, 22:00 = 102, 23:00 = 194; Oct 15 22:00 = 202. That is about 190 calls per
hour when the server is up, or two fetches of about 95 articles. Average call: 585 prompt and 250
completion tokens, which matches `SCORING_PROMPT` plus a JSON verdict (verified).
The DB holds 497 `news_articles` rows (463 scored) but 904 calls in the window, so articles are
scored more than once.

### 1.2 Inventory by trigger

| Caller | Trigger and config key | Model | Calls per day (server up 24h) | Status |
|---|---|---|---|---|
| news credibility scoring | `news_fetch` `*/30 * * * *`; `news.credibility.enabled`, `llm_scoring` | gpt-4o-mini | about 95 per fetch x 48 = **about 4,500** (bug, 3.3) | Verified |
| news admission gate and ingest | same job; `correlation.salience` | none (E5 embeddings) | 0 | Verified: no `complete` in path |
| correlation scan | `0 */4 * * *`; `correlation.push.*` | Haiku (`correlation.engine.model`) | up to 6 runs x 20 seeds = 120, 800 max tokens each | Inferred; runs because `dry_run: true` (push.py:111) |
| `goal_advance_sweep` | `*/15 * * * *`, hard-coded in `ze_automation/bootstrap.py:320`; advances every goal returned by `list_for_advance` | Sonnet/Haiku via GoalExecutor | depends on goals; dev DB has 3 open (2 `awaiting_gate`, 1 `planning`) | Not verified what `list_for_advance` returns |
| `session_summary` | `*/10`; `memory.session_summary` | Haiku | one per idle session with 2+ episodes, 5 per run max | Inferred |
| `memory_consolidation` | `0 2 * * *` | Haiku | bounded: 50 episodes, 10 sessions per run | Inferred |
| `dream_memory` | `0 3 * * *`; `dream.*` | Haiku synthesis + Sonnet 4.6 critic | up to 100 replay, 20 synth, 30 schema candidates; 30 min timeout | Inferred; the most expensive nightly job |
| `contacts_consolidation` | `0 3 * * *`; `contacts.consolidation` | Haiku | batches of 10 episodes, 50 max | Inferred |
| calendar interval assessment | `calendar_reminder_sync` `45 7 * * *`; `proactive.calendar` | Haiku | one per new or updated event, 150 max tokens | Verified in code |
| `insight_generation` | `0 7 * * 0` | Haiku | 1 per week, 400 max tokens; skips when evidence is sparse | Verified |
| goal narrative / suggestion / stuck / accountability | Sun 18:00, Sun 19:00, Tue 09:00, Mon 09:00 | via GoalPlanner (`goals/planner.py`) | weekly | Not verified which call each makes |
| `cost_reconciliation` | `*/15`, workflow scheduler | none (OpenRouter GET) | 96 runs x 50 GETs = **4,800 requests, 4,224 of them wasted** | Verified (3.2) |
| `inbound_poll` | every 5 min | System One + extractors per mail | 0 now: log shows `invalid_grant` | Verified |
| No LLM found | `morning_briefing`, `drift_sweep`, `stale_suspicion`, `hypothesis_decay`, `attention_arbitration`, `skills_recheck`, `quiet_hours_release`, `prune_notifications`, `held_write_expiry`, `cost_anomaly`, `checkpoint_pruning`, finance jobs (`llm_categorization: false`), `gmail_watch_renewal`, `recover_stale_campaigns` | | 0 | Verified by reading each file |

Startup: `AUTO_SEED_DEV_DATA` runs no LLM (ze-seed has no client calls). The only startup-driven spend
is **cron catch-up**: `ProactiveScheduler.register` and `add_cron_job` default `catch_up=True`,
and `_schedule_catch_ups` fires each job whose cron time passed since `last_started_at`, staggered.
Only the briefing sets `catch_up_max_age_hours` (6). After a night off, boot fires news, consolidation,
dream, contacts, correlation and the weekly jobs once each. This is why a fresh boot shows a news
burst: Tally's "about 120 gpt-4o-mini calls after a fresh-DB boot" is the first fetch (a real first
fetch, so correct) and every later fetch repeats it.

## 2. Per conversation turn

Turn = one WebSocket message through `invoke_raw_turn`. Non-eval, non-retry, non-trivial prompt
(`is_trivial_turn` is a greeting-style regex). Eval threads (`eval-*`) skip `write_memory`
side effects; Retry skips them too.

| # | Step | Call | Model | When | Skip / batch option |
|---|---|---|---|---|---|
| 1 | preprocess | transcription / image caption | gpt-audio / vision model | voice or image input only | none |
| 2 | embed_route | System One routing Choice | jev, about 1.6k prompt tok | every routed turn with 2+ enabled agents (`routing.py:_judge`) | check whether E5 can skip it when decisive (phase 160 skip path); not verified that it does today |
| 3 | decompose | Haiku decompose | Haiku, about 1.7k prompt tok, 2 attempts on failure | when the Choice does not trust a single agent or E5 is low-confidence (`is_compound`) | tighten trust (`choice_trust` is 0.5) |
| 4 | match_skills | System One skills Choice + Noul | jev | only when approved skills exist; **dev DB has 0 skills, so 0 calls** | already conditional |
| 5 | execute_tool | agent loop, 1..N calls (cap 20 tool calls) | agent model (Sonnet research/goals, Haiku others) | every turn | the real work; cache the system prompt |
| 6 | correlate | none in the turn (inline correlation uses stored hypotheses) | | | |
| 7 | synthesize | Haiku synthesis | `models.synthesis` (Haiku) | compound turns only | none |
| 8 | write_memory | commitment intake, 1 System One request | jev, about 1.2k prompt tok | every non-trivial turn | already skips trivial |
| 9 | write_memory | fallback fact extractor + Haiku loop gate | Haiku | only when intake is off, errors or returns an invalid answer | none needed |
| 10 | write_memory | fact value writer, loop title writer | Haiku | after a positive intake decision (fire-and-forget) | rare |
| 11 | write_memory | **event extractor** | Haiku, 400 max tokens, **awaited inline** | **every turn** that is not `[ERROR]` | gate on `is_trivial_turn`; merge with 12 |
| 12 | write_memory | **entity extractor** | Haiku, 300 max tokens, **awaited inline** | **every turn** that is not `[ERROR]` | merge with 11; or fold both into the System One intake |
| 13 | write_memory | contact proposal hook | none (reads agent proposals) | | |
| 14 | write_memory | history compaction | `models.synthesis` | when history reaches 70% of the context window | rare |
| 15 | after reply | session title | Haiku (`session_title`) | scheduled after **every** turn; skips once `title_source == "generated"`, so one call per session unless it fails | schedule only on the first turn |

Rough cost of the extras on a Sonnet turn (about $0.015 for the agent call): routing Choice and
intake are System One (price unknown, section 3.2); events + entities are about 2 x $0.0016 = $0.003,
about 20% on top of a Sonnet turn and about 100% on top of a Haiku turn. Steps 11 and 12 are the best
batching target: same input (`User said ... Assistant replied ...`), same model, two requests.

Dead code: `ze_memory/retriever.py:_generate_summary` ("summarize this interaction in one sentence")
is defined and never called. It is not a per-turn cost.

## 3. Attribution and `cost_usd`

### 3.1 Why rows are `unknown/unknown`

`CostTracker.record` reads `get_cost_context()` and falls back to `unknown/unknown`.
`set_flow_context` has four call sites: the eval routes, workflow execution
(`ze_automation/bootstrap.py:249`), and transcription. Nothing sets it for WebSocket turns or
`ProactiveScheduler` jobs.

- The `"user_message"` flow was set by the Telegram dispatcher, removed in Phase 45. The last
  `user_message` row is 2026-06-01 (verified: 4 days of rows, all May to June 1).
- `set_agent_context` only replaces fields when a context already exists
  (`telemetry/context.py:27`). On a WS turn there is none, so `set_agent_context("router")`,
  `("synthesis")` and the per-agent call in `execution.py` all silently do nothing.
- Cron jobs run in APScheduler tasks that never set a context. `asyncio.create_task` children inherit
  the context at creation, so one fix in the scheduler wrapper also covers news's background scoring task.
- System One rows go through the same tracker, so they inherit the same gap (36 of the 88 jev rows are unknown: the WS turns; the rest came from eval and workflow threads that did set a context).

Fix (all small, none in a plugin):
1. `invoke_raw_turn`: `set_flow_context("user_message", session_id=thread_id)` before the graph runs.
2. `set_agent_context`: create a context (`flow_type="unknown"`) when none exists.
3. `ProactiveScheduler._recording`: `set_flow_context("proactive", session_id=f"job:{job_id}")` and
   `set_agent_context(job_id)` before `fn()`. Same in the workflow scheduler's `schedule_job` wrapper.
4. Optional: tag System One calls `agent="system_one:<surface>"` so the surface is visible.

### 3.2 Why `cost_usd` is NULL

Verified in the DB and log:

- `cost_usd` is set only by `CostReconciler`, which backfills from `GET /generation`. Last costed
  row: 2026-06-25 22:36. Rows with cost: May 419/419, June 4,016/5,123, July to October 0 of 17,240.
- `fetch_pending` orders by `created_at ASC LIMIT 50`. 44 rows from 2026-06-11 to 06-25 get
  `Generation ... not found` on every attempt (11,598 `cost_fetch_failed` lines in the log, one per
  failing row per run). Every run since July logs `skipped=44 updated=6` (112 runs at `skipped=42
  updated=8`). Head-of-line blocking: the 44 permanent failures take the batch.
- **Unexplained**: the 6 rows that do not fail each run are the next oldest, yet they are still
  NULL in the DB after months. Each run reports `updated=6` for them. I could not reproduce or
  explain this without a live `GET /generation`. Check this before trusting the fix below;
  it may be a second bug (`update_cost` not persisting, or `total_cost` not a usable value).
- System One rows carry `generation_id = gen-dec-...`, which is not an OpenRouter generation. They
  will fail the same way once they reach the head of the queue (88 rows now).
- Side effect: `SpendBudgetChecker` prices unknown models, including `typesafe/jev-*`, at
  `DEFAULT_PRICING` ($5/$15). Fine while `budget:` is null; wrong if it is ever enabled.

Fix: add a retry cap. Either a `cost_attempts` column (migration, `zc*` chain) or, cheaper, restrict
`fetch_pending` to `created_at > now() - interval '3 days'` and to non-System-One rows; mark rows
older than that as unreconcilable. Log the first failure per row once, not every run. Then run the
one-GET repro above.

### 3.3 The news "new article" bug (root cause of 1.1)

`ze_news/store.py:124-141`:

```sql
INSERT INTO news_articles (...) VALUES (...)
ON CONFLICT (url) DO UPDATE SET fetched_at = now()
```
```python
if status == "INSERT 0 1":
    new_articles.append(article)
```

Postgres reports `INSERT 0 1` for each row inserted **or updated** by `DO UPDATE` (only `DO NOTHING`
reports `INSERT 0 0` on a conflict). Checked on a session-local temp table: the first insert and a
conflicting second insert both return `INSERT 0 1`. So `new_articles` is the whole feed on every
run. Consequences: every fetch re-runs credibility scoring (LLM), `dedup_new_articles`, the
admission gate (`_emit_via_source`) and `credibility_analysis` overwrites. `min_fetch_interval_minutes: 30`
does not help: it only stops a fetch within 30 minutes of the last one, and `fetched_at` is refreshed
by the same upsert.

Plugin fix, a follow-up per the user's guidance: use `RETURNING (xmax = 0) AS inserted`, or insert with
`ON CONFLICT DO NOTHING` and update `fetched_at` separately. Config-only mitigation today:
`news.credibility.llm_scoring: false` (status becomes `heuristic_only`, no LLM) or
`news.credibility.enabled: false`.

## 4. Dev profile

Today there is no profile or overlay. `ZeApiSettings.config` re-reads
`config_dir/config.yaml` on every access, and `config_dir` is a pydantic setting, so `CONFIG_DIR=<dir>`
already works with zero code, at the price of a forked copy of `config.yaml`.

Proposal: `apps/ze-api/config/profiles/quiet.yaml`, deep-merged over `config.yaml` when
`ZE_PROFILE=quiet` (a 15-line change in `_load_yaml` / `config`). `make dev`, `make dev-eval`, `make
dev-full` and the e2e throwaway-DB targets would set it; an empty `ZE_PROFILE` keeps today's behavior.

```yaml
# profiles/quiet.yaml
news:
  fetch_schedule: "0 8 * * *"        # daily; or enabled: false and use the refresh tool on demand
  credibility:
    llm_scoring: false                # heuristics only, no LLM
correlation:
  push: { enabled: false, dry_run: false }   # scan returns early, no LLM
proactive:
  insights: { enabled: false }
  goal_suggestion: { enabled: false }
  goal_narrative: { enabled: false }
  accountability: { enabled: false }
  calendar: { sync_enabled: false }
dream: { enabled: false }
memory:
  consolidation: { enabled: false }
  session_summary: { enabled: false }
contacts:
  consolidation: { nightly_cron: "0 3 1 1 *" }   # effectively off
```

Plus one code key that does not exist yet: `proactive.catch_up: false` (global) read by
`ProactiveScheduler`, so a boot fires nothing. Without it the profile still re-fires every missed
job at boot.

| Setting | Saves (server up 24h) | Config only? |
|---|---|---|
| `news.credibility.llm_scoring: false` | about 4,500 gpt-4o-mini calls, about $1.07/day; removes all `unknown` gpt rows | yes |
| `news.fetch_schedule` daily | cuts fetches 48 to 1 (embedding + network work, admission-gate churn) | yes |
| `correlation.push.dry_run: false` | up to 120 Haiku calls/day | yes |
| `dream.enabled: false` | one nightly Haiku + Sonnet critic run (bounded by the caps in config; not sampled) | yes |
| consolidation, session_summary, contacts | nightly and 10-minute Haiku calls, bounded | yes |
| weekly insights / goal jobs | about 5 calls per week | yes |
| `proactive.catch_up: false` | removes the boot-time burst of everything missed | needs a code key |

Not in the profile: `system_one`, routing, skills and commitment intake. They are per-turn and
calibrated; turning them off changes the behavior under test. Evals want them on.

## 5. Ranked cheap wins

| # | Change | Where | Est. saving | Effort |
|---|---|---|---|---|
| 1 | `news.credibility.llm_scoring: false` in the dev profile (config), then fix `upsert` "new" detection (plugin follow-up) | config; `ze_news/store.py` | about 4,500 calls/day (about $1.07/day) with server up; after the fix, only first-seen articles (tens per day) | config: minutes; fix: 5 lines + test |
| 2 | Cost context for WS turns, jobs and System One (3.1) | `turn.py`, `telemetry/context.py`, scheduler wrapper | 0 $ directly; makes every other number measurable | small |
| 3 | Reconciler retry cap and recency window, then the one-GET repro for the 6 stuck rows (3.2) | `telemetry/postgres.py`, `reconciler.py` | stops 4,224 failing GETs per day; restores real `cost_usd` | small + a migration if an attempts column is used |
| 4 | Gate events + entities on `is_trivial_turn` and merge into one Haiku call | `ze_memory/extractor.py`, `nodes/memory.py` | 1 to 2 Haiku calls per turn (about $0.003/turn), and one inline round trip off the reply tail | small |
| 5 | `correlation.push.dry_run: false`, or skip the LLM in dry-run | config / `push.py:111` | up to 120 Haiku calls/day | config |
| 6 | `proactive.catch_up` global switch and per-job max age (news, consolidation, dream) | `ze_proactive/scheduler.py` | removes the boot burst | small |
| 7 | Skip the System One routing Choice when E5 is decisive | `routing/router.py` | one jev call per turn (price unknown) | needs a calibration pass; do not do blind |
| 8 | Schedule the session title only until it exists | `turns.py` | removes retry calls after a failed first attempt | trivial |
| 9 | Verify `goal_advance_sweep` (`list_for_advance`) does not call the LLM for goals with no runnable milestone; make its `*/15` cron configurable | `ze_automation` | unknown; could be the largest unattended Sonnet cost with active goals | read + measure |
| 10 | Price System One in `pricing.py` or give it `generation_id=None` | `telemetry/pricing.py`, `openrouter/system_one.py` | correctness of `budget:` and the reconciler | trivial |

Follow-ups for plugin maturity (not redesigns): news credibility as a System One judgment instead of a
gpt-4o-mini call (the user's note; needs a calibration set like the other surfaces), a real
"new article" signal from `upsert`, and `llm_categorization` for finance when it is turned on.

## 6. Not verified, and what blocks it

- The 6 reconciler rows that report `updated` but stay NULL (3.2). Needs one `GET /generation` against
  OpenRouter; I made no external calls.
- System One price. `typesafe/jev` has no entry in `pricing.py` and its rows carry no usable cost.
- Dream, consolidation, contacts, goal and weekly job volumes are code-bounded estimates. The last
  7 days contain none of them (the server was not up at those times), so the log has no sample.
- The dev server log ends 2026-10-12; I did not read logs from the other floors.

## Evidence

Queries ran through `docker exec ze-postgres-1 psql` with `default_transaction_read_only = on`.

- Daily volume and rows with cost: `select date(created_at), count(*), count(cost_usd) from llm_cost_log group by 1`.
- Model and flow breakdown: `group by model, agent, flow_type` over 7 days and all time.
- Pending rows: `where cost_usd is null and generation_id is not null` = 18,184; first 44 by `created_at`
  are the permanent failures; offset 44 starts at 2026-06-25 22:35:21.
- Log: `cost_reconcile_done skipped=44 updated=6` on every run from July; 11,598 `cost_fetch_failed ... not found`.
- Code: `ze_news/store.py:124-141`, `ze_news/jobs/fetch.py:84-94`, `ze_core/telemetry/context.py`,
  `ze_core/telemetry/postgres.py:fetch_pending`, `ze_core/orchestration/nodes/memory.py:216-237`,
  `ze_correlation/push.py:111`, `ze_proactive/scheduler.py:51-92,129-165`.
