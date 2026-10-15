# Data Model: Interruption Governor (part 1)

## Python types (`core/contracts/ze-proactive/ze_proactive/types.py`)

```text
PushClass = Literal["requested", "accountability", "discretionary"]
Urgency   = Literal["low", "normal", "high"]
Delivery  = Literal["delivered", "held", "released", "suppressed", "failed"]
PushOutcome = Literal["delivered", "held", "suppressed_budget", "duplicate", "deduped", "failed"]

@dataclass(frozen=True)
PushKind:
  event_type: str      # unique across the registry; matches notifications.event_type
  push_class: PushClass
  urgency: Urgency
  source: str          # notifications.source (e.g. "calendar", "goals", "personal")
  __post_init__ → push_kinds.register(self)   # PushPolicyError on conflicting re-registration

@dataclass(frozen=True)
QuietHoursSetting:
  enabled: bool
  start: time | None
  end: time | None
  timezone: str | None   # IANA key
  updated_at: datetime | None

@dataclass(frozen=True)
JobRun:
  job_id: str
  last_started_at: datetime
  last_finished_at: datetime | None
  last_status: Literal["running", "ok", "error"]
```

`NotificationRow` and the wire `Notification` (`ze_proactive.types`) gain `push_class`, `urgency`, `delivery`. `ze_agents.interface.types.Notification` gains `buzz: bool = True`; `urgency` is typed `Literal["low","normal","high"]`.

Registering the same `event_type` again with an identical `PushKind` is a no-op (module re-import in tests); a different class, urgency or source raises `PushPolicyError`.

## Governor decision (`ze_proactive/governor.py`)

```text
Decision = Literal["deliver", "hold", "suppress"]

decide(kind, *, quiet_now, budget_won) -> Decision
  requested                         → deliver
  discretionary and not budget_won  → suppress   (even in quiet hours: the budget check runs first, so the daily cap holds)
  quiet_now                         → hold
  accountability                    → deliver
  discretionary and budget_won      → deliver
```

Outcome mapping in `notify()`:

| Step | Outcome | Row | Interface |
|---|---|---|---|
| `dedup_hours` hit | `deduped` | none | none |
| discretionary, key already claimed | `duplicate` | none | none |
| discretionary, budget full | `suppressed_budget` | `delivery='suppressed'` | silent `notification` frame |
| hold | `held` | `delivery='held'` | silent `notification` frame |
| deliver ok | `delivered` | `delivery='delivered'`, `delivered_at=now()` | `push(Notification(buzz=True))` |
| deliver raised | `failed` | `delivery='failed'`; budget claim released | — |
| no store | `failed` | none | none (log `proactive_notify_no_store`) |

## Postgres (`zpro004_interruption_governor`, revises `zpro003`)

### `notifications` (altered)

| Column | Type | Rule |
|---|---|---|
| `push_class` | `TEXT NOT NULL` | `CHECK (push_class IN ('requested','accountability','discretionary'))`; backfill `'accountability'` |
| `urgency` | `TEXT NOT NULL` | `CHECK (urgency IN ('low','normal','high'))`; backfill `'normal'` |
| `format` | `TEXT NOT NULL DEFAULT 'text'` | `CHECK (format IN ('text','markdown','html'))` |
| `actions` | `JSONB NOT NULL DEFAULT '[]'` | list of `{label, payload, row}` |
| `delivery` | `TEXT NOT NULL` | `CHECK (delivery IN ('delivered','held','released','suppressed','failed'))`; backfill `'delivered'` |
| `delivered_at` | `TIMESTAMPTZ` | backfill `created_at` for existing rows |

Index: `CREATE INDEX notifications_held_idx ON notifications (created_at) WHERE delivery = 'held'`.

Backfill then `SET NOT NULL` (columns added nullable, updated, then constrained, in one migration).

### `interruption_settings` (new, single row)

| Column | Type | Rule |
|---|---|---|
| `id` | `BOOLEAN PRIMARY KEY DEFAULT TRUE` | `CHECK (id)` |
| `quiet_hours_enabled` | `BOOLEAN NOT NULL DEFAULT FALSE` | |
| `quiet_start` | `TIME` | |
| `quiet_end` | `TIME` | |
| `timezone` | `TEXT` | |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | |

`CHECK (NOT quiet_hours_enabled OR (quiet_start IS NOT NULL AND quiet_end IS NOT NULL AND timezone IS NOT NULL AND quiet_start <> quiet_end))`. Upsert: `INSERT … ON CONFLICT (id) DO UPDATE`. No row = disabled.

### `proactive_job_runs` (new)

| Column | Type |
|---|---|
| `job_id` | `TEXT PRIMARY KEY` |
| `last_started_at` | `TIMESTAMPTZ NOT NULL` |
| `last_finished_at` | `TIMESTAMPTZ` |
| `last_status` | `TEXT NOT NULL CHECK (last_status IN ('running','ok','error'))` |

`record_start` upserts `(job_id, now(), NULL, 'running')`; `record_finish` updates `last_finished_at`, `last_status`.

Data portability: `interruption_settings` is user data. It gets a `DataDomain("proactive.interruption_settings", …)` in a new `apps/ze-api/ze_api/interruption_domain.py`, following `feedback_domain.py`, added to `all_domains` in `container.py` (export, import, delete = row removed = quiet hours off). `notifications` has no data domain today; that pre-existing gap is out of scope. `proactive_job_runs` is operational and not exported.

## State: notification delivery

```text
(notify) ──deliver──▶ delivered
        ├─hold─────▶ held ──release job──▶ released
        ├─suppress─▶ suppressed            (terminal)
        └─raise────▶ failed                (terminal)
```
