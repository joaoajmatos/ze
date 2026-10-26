# ze-notifications

Push notification abstraction for Ze. Decouples notification delivery from the rest of the system — currently implemented via [ntfy](https://ntfy.sh).

## Role in Ze

When the user is away from the web app, Ze still needs to reach them — morning briefings, calendar reminders, stuck goal alerts, correlation insights. `ze-notifications` abstracts push delivery so the rest of the system doesn't depend on a specific provider.

### Key features

- `Notifier` protocol — swappable delivery backend
- `NtfyNotifier` — HTTP push via ntfy with priority, tags, and deep-link data
- Priority levels from silent background sync to urgent alerts

### Integration

`ze-api` builds `NtfyNotifier` in `_build_push_notifier` (`ze_api/wiring/container.py`) when `NTFY_TOPIC` is set, and passes it to `NativeAppInterface`. `ProactiveNotifier` sends through that interface and holds no `NtfyNotifier` of its own. When the WebSocket is disconnected, outbound messages fall back to ntfy push; when connected, they flow over WebSocket instead.

## Responsibilities

| Module | What it provides |
|---|---|
| `notifier.py` | `Notifier` Protocol — the interface all delivery backends must satisfy |
| `ntfy.py` | `NtfyNotifier` — delivers notifications via ntfy HTTP API |
| `types.py` | `Notification` dataclass with priority, tags, and deep-link `data` |

## Dependencies

No Ze package dependencies. Depends only on: `aiohttp`.

## Usage

```python
from ze_notifications.ntfy import NtfyConfig, NtfyNotifier
from ze_notifications.types import Notification

config = NtfyConfig(base_url="https://ntfy.sh", topic="ze-abc123", token="...")
notifier = NtfyNotifier(config, session)

await notifier.push(Notification(
    title="Morning briefing",
    body="Here's your day...",
    priority=3,
    data={"navigate": "briefing"},
))
```

The React web app (`ze-web`) uses browser URL routing for in-app navigation. ntfy push notifications alert the user when the app is closed; tapping opens the app in the browser.

## Configuration

| Variable | Description |
|---|---|
| `NTFY_BASE_URL` | ntfy server URL (e.g. `https://ntfy.sh`) |
| `NTFY_TOPIC` | Your topic name — keep non-guessable for ntfy.sh. Empty means no push. |
| `NTFY_TOKEN` | Bearer token; `NtfyNotifier` refuses to start for an `ntfy.sh` URL without it |

## Notification priorities

| Value | Meaning |
|---|---|
| 1 | min — silent background sync |
| 2 | low |
| 3 | default |
| 4 | high |
| 5 | urgent |

`NativeAppInterface` maps a notification's urgency to a priority: `low` is 2, `normal` is 3, and `high` is 5.

## Testing

From the repo root:

```bash
make test-notifications
```

See [docs/testing.md](../../docs/testing.md).
