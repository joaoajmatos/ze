# ze-trading212

Trading212 REST API client — account, portfolio, orders, and history.

## Role in Ze

`ze-finance` reads portfolio data from Trading212 through this package. The package knows the Trading212 API and nothing about Ze's domain. It has no Ze dependencies.

### Key features

- `Trading212Client` — async `httpx` client for the Trading212 v0 API
- Reads: account info, cash, portfolio, orders, order history, dividend history, transaction history, instruments
- Order calls: limit order, market order, cancel order
- Live and demo endpoints, chosen by one setting

### Integration

`Trading212Client.from_settings()` returns `None` when no API key is set, so the Finance plugin simply skips this source. `ze-api` creates the client and passes it to `FinancePlugin`, which wraps it in `Trading212DataSource`.

## Responsibilities

| Module | What it provides |
|---|---|
| `client.py` | `Trading212Client` and the `from_settings()` factory |
| `settings.py` | `Trading212Settings` — reads the key and demo flag from env or `apps/ze-api/.env` |

## Dependencies

`httpx`, `pydantic-settings`. No Ze packages.

## Configuration

| Variable | Description |
|---|---|
| `TRADING212_API_KEY` | API key from Trading212. Empty disables the integration |
| `TRADING212_DEMO` | `true` to use the demo endpoint (default `false`) |

## Testing

From the repo root:

```bash
make test-trading212
```

See [docs/testing.md](../../docs/testing.md).
