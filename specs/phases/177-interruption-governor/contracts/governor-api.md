# Contract: Governor Python API (`ze_proactive`, re-exported by `ze_sdk.proactive`)

## Declaring a kind (module level, in the package's `push_kinds.py`)

```python
from ze_sdk.proactive import PushKind

INSIGHT = PushKind(event_type="insight", push_class="discretionary", urgency="normal", source="personal")
```

- `event_type` is unique across the process. Re-creating an identical kind is a no-op; a conflicting one raises `PushPolicyError`.
- `registered_push_kinds() -> dict[str, PushKind]`.
- Governor-owned kind: `QUIET_HOURS_SUMMARY = PushKind("quiet_hours_summary", "accountability", "normal", "proactive")` (urgency at send time = highest held urgency; see `deliver_held`).

## Sending

```python
outcome: PushOutcome = await notifier.notify(
    INSIGHT,
    title="New insight: Health",
    body=text,
    target_type="insight", target_id=str(row_id),   # both or neither (table CHECK)
    budget_key=f"insight:{row_id}",                # REQUIRED for discretionary, ignored otherwise
    actions=(Action(label="…", payload="…"),),      # optional, kept through hold/release
    format="text" | "markdown" | "html",
    dedup_hours=None | float,                       # existing exists_recent() dedup, checked first
)
```

`PushOutcome = "delivered" | "held" | "suppressed_budget" | "duplicate" | "deduped" | "failed"`.

Errors: `PushPolicyError` — discretionary without `budget_key`; unknown/unregistered kind object (not created via `PushKind`).

`notify` never raises for delivery failures; it returns `failed` and logs `proactive_push_failed`.

## Other notifier methods

- `remaining_budget() -> int` — `max_per_day - count_sent_within_hours(ATTENTION_PUSH_EVENT_KEY, 24)`, floored at 0; fails open (returns `max_per_day`) on store error.
- `deliver_held() -> int` — used by `QuietHoursReleaseJob`; returns the number of released rows (0 → no summary).
- `ProactiveNotifier.push` and `ProactiveNotifier.push_notification` **do not exist**.

## Constructor

```python
ProactiveNotifier(
    interface: AppInterface,
    notification_store: NotificationStore | None,
    *,
    push_log: PushLogStore | None = None,          # None → budget fails open (tests)
    settings_store: InterruptionSettingsStore | None = None,   # None → quiet hours off
    max_discretionary_per_day: int = 5,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
)
```

## Pure rule

`ze_proactive.governor.decide(kind, *, quiet_now: bool, budget_won: bool | None) -> Literal["deliver","hold","suppress"]` — table in `data-model.md`. `budget_won` is `None` for non-discretionary kinds.

## AppInterface change (`ze_agents.interface.types.Notification`)

- `urgency: Literal["low","normal","high"] = "normal"`
- `buzz: bool = True` — `NativeAppInterface.push` sends ntfy only when `buzz` is true and the client is offline. `push()` never checks quiet hours itself: the governor already decided (a requested push arrives with `buzz=True` during quiet hours; held items arrive at release with `buzz=False`). The quiet-hours check in `NativeAppInterface` applies only to the reply and confirmation ntfy hops (C1, C2).
- ntfy priority: low 2, normal 3, high 5.

## Silent frame

Held and suppressed rows go through `AppInterface.push` with `Notification.delivery` = `held` / `suppressed`. `NativeAppInterface.push` then emits only the existing `notification` WS frame (with the new fields `push_class`, `delivery`): no chat message, no action frames, no ntfy. At release, rows go through `push` again with `delivery="released"`, `buzz=False`, as a full delivery.
