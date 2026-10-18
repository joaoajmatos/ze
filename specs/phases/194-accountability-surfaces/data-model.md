# Data Model: Accountability Surfaces (B4)

## Migration `zc040_channel_poll_outcome` (ze-personal, revises `zc039`)
```sql
ALTER TABLE user_channel_watermarks
  ADD COLUMN IF NOT EXISTS last_outcome    TEXT NULL,   -- 'ok' | 'auth_failed' | 'failed'
  ADD COLUMN IF NOT EXISTS last_outcome_at TIMESTAMPTZ NULL;
```
Downgrade drops both columns. Outcome writes UPDATE an existing row; with no row they INSERT `last_polled_at = now() - 24 h` (the store's `DEFAULT_LOOKBACK_HOURS`), never `now()`.

## Domain types
- `ActionSubjectKind` (ze-memory `action_records/types.py`): `goal | workflow | workflow_run | workspace_run` → context key map (closed).
- `PollOutcome` (ze-personal `channels/types.py`): `StrEnum ok | auth_failed | failed`.
- `ChannelPollStatus` (ze-personal): `watermark: datetime | None`, `last_outcome: PollOutcome | None`, `last_outcome_at: datetime | None`.
- Channel state (ze-api mapping, not stored): `connected | needs_reauth | error | off | unknown` (push channels; no outcome yet).

## Read shapes (ze-api schemas)
- `ActionRecordItem`: id, action_type, actor, producer_plugin, lifecycle, outcome, summary, touched {domain, record_id}, occurred_at, failure_code.
- `ActionRecordPage`: items, next_cursor.
- `CollisionLogEntrySchema`: unchanged (moved).
- `ModelSettingsResponse`: complexity_enabled, simple_max, agents [{name, model, model_simple}].
- `ChannelStatusResponse`: google_configured, channels [{channel_id, channel_type, handle, display_name, state, last_sync_at, push}].
