# ze-messenger

Cross-channel messenger — reads, drafts, and sends messages, and handles inbound mail.

## Role in Ze

This plugin gives Ze an inbox. The `messenger` agent reads, searches, drafts, sends, and archives mail through whatever channels are registered. The plugin also watches those channels for new mail, decides which messages matter, and feeds them to memory and to the correlation engine.

Channels themselves live elsewhere. The contract is in `ze-communication`, and `GmailChannel` is in `ze-google`. See [docs/channels.md](../../docs/channels.md) for the full pipeline.

### Key features

- `MessengerAgent` with `list_emails`, `get_email`, `draft_email`, `send_email`, and `archive_email`
- Thread-aware send routing: a reply uses the channel that owns the thread
- `InboundPollingJob` polls channels that do not push (default every 5 minutes)
- `InboundMessageProcessor` classifies each sender (known contact, replied-to, unknown human, automated) and gates episodes, facts, signals, and notifications
- `MessagingSignalSource` gives the correlation engine one signal per significant message
- Outbound send ledger (`messenger_outbound_sends`) and an action record for each send

### Integration

`MessengerPlugin` is a `ZePlugin` declared under the `ze.plugins` entry point. It returns the Gmail channel from `channels()`, registers its agent and tools through `agent_module_paths()`, and owns the `zmsg` migration chain. When `PUBLIC_URL` is set, Gmail pushes mail through the webhook route, and `GmailWatchRenewalJob` renews the Gmail watch every Sunday. The plugin reads `UserChannelStore` and `ThreadChannelMap` from `ze-personal`.

## Responsibilities

| Module | What it provides |
|---|---|
| `plugin.py` | `MessengerPlugin` — channels, jobs, signal source, migrations |
| `agents/messenger/` | `MessengerAgent` and its Gmail tools |
| `inbound/processor.py` | `InboundMessageProcessor` and sender classification |
| `jobs/inbound_poll.py` | `InboundPollingJob` |
| `jobs/gmail_watch_renewal.py` | `GmailWatchRenewalJob` |
| `signals.py` | `MessagingSignalSource` |
| `outbound/` | Send ledger store, types, and action-record adapter |
| `migrations/` | `zmsg001` — creates `messenger_outbound_sends` |

## Dependencies

`ze-sdk`, `ze-google`, `ze-personal`.

## Configuration

| Key in `config.yaml` | Description |
|---|---|
| `messaging.automated_senders` | Extra sender patterns to treat as automated (regex allowed) |
| `proactive.inbound_poll_interval_seconds` | Polling interval (default 300) |

Gmail push also needs `PUBLIC_URL` and `GMAIL_PUBSUB_TOPIC`.

## Testing

From the repo root:

```bash
make test-messenger
```

See [docs/testing.md](../../docs/testing.md).
