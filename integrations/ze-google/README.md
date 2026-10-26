# ze-google

Shared Google OAuth2 credentials for Ze. Provides authenticated service client factories for Google APIs, plus the Gmail channel.

## Role in Ze

Google Calendar and Gmail are the two primary external services Ze integrates with. `ze-google` wraps OAuth2 refresh-token credentials and exposes typed client factories so plugins never handle token refresh or scope management themselves.

### Key features

- Single refresh token covers Calendar and Gmail scopes
- Automatic access-token refresh — no manual token management
- `from_settings()` factory — returns `None` when env vars are absent (graceful disable)

### Integration

Satisfies the `ZeIntegration` protocol structurally. Plugins declare `GoogleCredentials` in `integration_types()`; `ze-api` bootstrap calls `from_settings` once and injects the result into `MessengerPlugin` and `CalendarPlugin`. Credentials are obtained once via `make google-auth`.

## Responsibilities

| Module | What it provides |
|---|---|
| `auth.py` | `GoogleCredentials`, `SCOPES`, `calendar()` and `gmail()` client factories |
| `gmail_channel.py` | `GmailChannel` — the Gmail `InboundChannel`: `send()`, `get_thread()`, `poll_new_messages()`, `register_push()` (Gmail watch). `supports_push` is true when a public URL is set |
| `auth_errors.py` | `is_auth_failure()` — true for a token refresh failure or a 401 from Google, so callers need not import `google.auth` |
| `settings.py` | `GoogleSettings`, `get_google_settings()` — OAuth env vars |
| `webhook.py` | `GmailWebhookVerifier` — verifies Pub/Sub push OIDC tokens |

## Dependencies

Ze: `ze-communication` (channel types and the webhook verifier base) and `ze-agents`. Third party: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`, `pydantic-settings`, `structlog`.

## Usage

```python
from ze_google.auth import GoogleCredentials

creds = GoogleCredentials(
    client_id=...,
    client_secret=...,
    refresh_token=...,
)
calendar = creds.calendar()
gmail = creds.gmail()
```

Credentials are wired into the container in `ze-api` and injected into `ze-calendar` and the Gmail channel.

## Setup

Run the one-time OAuth2 flow from the repo root:

```bash
make google-auth
```

The script needs `client_secrets.json` (an OAuth 2.0 Desktop client) in the repo root. It opens a browser for consent, then prints the refresh token inside a `fly secrets set GOOGLE_REFRESH_TOKEN=...` line. It does not write any file. For a local run, copy the token into `apps/ze-api/.env` as `GOOGLE_REFRESH_TOKEN`, with `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

## Testing

From the repo root:

```bash
make test-google
```

See [docs/testing.md](../../docs/testing.md).
