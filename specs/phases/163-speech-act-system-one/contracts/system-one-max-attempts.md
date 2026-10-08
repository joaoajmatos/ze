# Contract delta: `SystemOneClient.evaluate(max_attempts=)`

**Feature**: `163-speech-act-system-one` (amends 162 [system-one-client.md](../../162-system-one-client/contracts/system-one-client.md))

```python
@runtime_checkable
class SystemOneClient(Protocol):
    async def evaluate(
        self,
        state: str | dict,
        questions: dict[str, SystemOneQuestion],
        *,
        max_attempts: int | None = None,
    ) -> SystemOneResult: ...
```

| `max_attempts` | `OpenRouterSystemOneClient` behavior |
|---|---|
| `None` | 162 behavior: up to `len(_BACKOFFS)` attempts with 1/2/4 s backoff on retryable status |
| `1` | exactly one POST, no `asyncio.sleep`; 429/529 → skip `overload`; other retryable/≥400 → skip `error` |
| `n > 1` | up to `min(n, len(_BACKOFFS))` attempts |
| `< 1` | skip `invalid_request`, no network |

`DisabledSystemOneClient.evaluate` accepts the keyword and returns skip `disabled`. Hard cut: the Protocol, both implementations and every test fake change together. No `**kwargs` passthrough.
