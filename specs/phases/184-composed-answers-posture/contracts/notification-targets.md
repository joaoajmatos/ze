# Contract: notification targets

Normative for FR-017, FR-018 and FR-020. `target_type` stays an open string (plugins add their own); this table lists every value in the codebase after this phase and what the client opens. `target_parent_id` is new (`zpro005`).

| `target_type` | `target_id` | `target_parent_id` | Emitted by | Client opens (phase 186+ paths) |
|---|---|---|---|---|
| `open_loop` | loop id | — | `ze_worldstate/surfacing.py` (drift push) | World, loop selected |
| `hypothesis` | hypothesis id | — | `ze_correlation/push.py` | Mind (entity view, phase 189); World until then |
| `goal` | goal id | — | `goals/executor.py`, `goals/proposal.py` | `/doing/goals/:target_id` |
| `goal_gate` | gate id | **goal id** (new) | `goals/executor.py` gate push | `/doing/goals/:target_parent_id` (gate first) |
| `goal_suggestion` | suggestion id | — | `jobs/goal_suggestion.py` | `/doing` |
| `workflow_execution` (renamed from `workflow_run`) | **execution id** (was the workflow id) | **workflow id** (new) | `ze_automation/bootstrap.py` failure handler | `/doing/workflows/:target_parent_id?execution=:target_id` |
| `held_write` | held write `request_id` | — | `holds/resumer.py` | World › Needs you (the card for `request_id`) |
| `workspace_run` | run id | — | `ze_api/wiring/container.py` | `/doing` › Runs |
| `chat_thread` | thread id | — | `ze_api/api/ws/confirmation.py` | `/ask/:target_id` |
| `reminder` (plugin) | reminder id | — | `ze_calendar/reminders/*` | World |
| `person` (plugin) | contact id | — | `ze_personal/jobs/contacts.py` | Mind › People |
| `insight` (plugin) | insight id | — | `ze_personal/jobs/insights.py` | Mind |

Until the place pages land (phases 186–190), ze-web maps these onto the interim paths from phase 183 (`/doing/goals/:id`, `/doing/workflows/:id`, `/`, `/mind`); the mapping lives in one function (`widgets/app-shell/lib/notification-format.ts` `notificationHref`) so each place phase edits one place.

## Store and wire

- `notifications.target_parent_id TEXT NULL` (`zpro005_notification_parent.py`, `down_revision = "zpro004"`; downgrade drops the column).
- `ProactiveNotifier.notify(kind, title, body, *, target_type=None, target_id=None, target_parent_id=None, …)`; `_notify`, `notify_goal`-style helpers and the quiet-hours held release pass it through.
- `NotificationRow.target_parent_id`, `Notification.target_parent_id` (default `None`), `PostgresNotificationStore.create` and `list_page`/`list_held` select it.
- `notification` WS frame (`ze_api/interface/native.py`) adds `"target_parent_id"`; `NotificationItem` adds `target_parent_id: str | None`; `make codegen`.
- `exists_recent` dedup is unchanged (parent not in the key).
