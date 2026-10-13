# Contract: Quiet hours REST + notification list delta

Router: `apps/ze-api/ze_api/api/routes/notifications.py` (prefix `/api/v0/notifications`, `require_api_key`). Schemas in `ze_api/api/schemas.py`.

## GET /api/v0/notifications/quiet-hours

`operation_id="getQuietHours"`, `summary="Get quiet hours"`, `description="The user's quiet-hours setting, whether it is active now, how many pushes are held, and the daily budget for unprompted pushes."`

200 `QuietHoursResponse`:

```json
{
  "enabled": true,
  "start": "23:00",
  "end": "08:00",
  "timezone": "Europe/Lisbon",
  "active_now": false,
  "held_count": 0,
  "max_discretionary_per_day": 5
}
```

No saved row → `{"enabled": false, "start": null, "end": null, "timezone": null, "active_now": false, "held_count": <n>, "max_discretionary_per_day": 5}`.

## PUT /api/v0/notifications/quiet-hours

`operation_id="updateQuietHours"`, `summary="Update quiet hours"`, `description="Save the quiet-hours window. While active, only reminders the user set are pushed; other pushes are held and released when quiet hours end."`

Body `QuietHoursUpdate`:

```json
{ "enabled": true, "start": "23:00", "end": "08:00", "timezone": "Europe/Lisbon" }
```

- `start`, `end`: `^([01]\d|2[0-3]):[0-5]\d$` or null.
- `timezone`: valid `zoneinfo` key or null.
- `enabled: true` requires all three non-null and `start != end`.
- `enabled: false` keeps whatever times are sent (so the form can remember them).

200 → `QuietHoursResponse` (fresh `active_now`, `held_count`). 422 → FastAPI validation shape; custom checks raise `RequestValidationError`-style `detail` entries with `loc` `["body","start"|"end"|"timezone"]` so the form can place messages.

## NotificationItem delta (GET /api/v0/notifications)

Adds:

```json
{ "push_class": "discretionary", "delivery": "suppressed" }
```

`delivery ∈ delivered | held | released | suppressed | failed`; `push_class ∈ requested | accountability | discretionary`.

## Client

`make codegen` regenerates `packages/ze-client/src/generated/*` exposing `getQuietHours()`, `updateQuietHours()`, and the new `NotificationItem` fields. Generated files are committed.
