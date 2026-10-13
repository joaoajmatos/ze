# Contract: `list_stuck`

Signature and `StuckGoal` unchanged (`idle_days: int`, `cooldown: int`) → `list[StuckGoal]`.

## Gate query (replaces the second `conn.fetch` in `PostgresGoalStore.list_stuck`)

```sql
SELECT DISTINCT ON (g.id)
    g.id, g.title, g.objective, g.success_condition, g.time_horizon,
    g.status, g.type, g.retrospective_text,
    g.last_stuck_alert_at, g.created_at, g.updated_at,
    vg.id AS gate_id, vg.goal_id AS gate_goal_id, vg.after_sequence,
    vg.title AS gate_title, vg.status AS gate_status, vg.context_summary,
    vg.plan_summary, vg.user_feedback, vg.fired_at, vg.resolved_at,
    vg.created_at AS gate_created_at,
    EXTRACT(DAY FROM now() - vg.fired_at)::int AS gate_idle_days,
    ( SELECT title FROM goal_milestones
      WHERE goal_id = g.id AND status IN ('completed','skipped')
      ORDER BY completed_at DESC NULLS LAST LIMIT 1 ) AS last_milestone_title
FROM goals g
JOIN goal_gates vg
  ON vg.goal_id = g.id
 AND vg.status IN ('pending', 'awaiting_approval')
 AND vg.fired_at IS NOT NULL
WHERE g.status = 'awaiting_gate'
  AND (g.last_stuck_alert_at IS NULL
       OR g.last_stuck_alert_at < now() - ($1 || ' days')::interval)
ORDER BY g.id, vg.fired_at ASC
```

The select list is the existing one. Only the join condition (`fired_at IS NOT NULL`), `DISTINCT ON` and the `ORDER BY` change; the outer `ORDER BY vg.fired_at` is dropped (Python re-sorts by `idle_days` descending, as today).

## Python guard

```python
fired_at = r["fired_at"]
if fired_at is None:
    log.warning("list_stuck_open_gate_without_fired_at", goal_id=str(r["id"]))
    continue
```

before any `.tzinfo` access. Unreachable after the SQL change; it exists so a future query edit cannot reintroduce the crash.

## Consumers (behavior after fix)

- `StuckGoalJob.run`: no exception for multi-gate goals; one alert per goal; `mark_stuck_alerted` per goal.
- `PriorityView.rank`: `goal` is in `sources_succeeded`, goal items present.
- `score_goal`: unchanged. `idle_days` is the days since the earliest fired open gate.

## Postgres test matrix (`tests/pg/test_stuck_goals.py`)

| Case | Expect |
|---|---|
| dev shape: 1 `awaiting_approval` fired 10 days ago + 3 unfired `pending` + 1 `approved` | one `awaiting_gate` entry, `idle_days == 10`, gate id is the awaiting one; no raise |
| two fired open gates (12 and 5 days ago) | one entry, `idle_days == 12` |
| only unfired gates | no entry, no raise |
| active goal, last milestone 20 days ago, `idle_days=7` | one `active` entry (unchanged) |
| `last_stuck_alert_at = now() - 3 days`, cooldown 14 | skipped |
| `list_stuck(0, 0)` as `PriorityView` calls it | does not raise |
| `PriorityView.rank()` with real stores on the dev shape | `sources_failed == set()`, goal item present |
| `StuckGoalJob.run()` with a recording notifier on the dev shape | one `push_notification`, `last_stuck_alert_at` set |
