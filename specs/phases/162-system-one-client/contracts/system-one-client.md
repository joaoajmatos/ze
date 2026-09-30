# Contract: SystemOneClient

**Feature**: `162-system-one-client`  
**Verbatim**: `SystemOneClient`, `NLIClient`, `LLMClient`, `ze_sdk`, `system_one`

## Placement

| Piece | Module |
|---|---|
| Protocol + request/result dataclasses | `ze_agents.system_one` |
| Re-export | `ze_sdk` (`SystemOneClient` next to `NLIClient`) |
| HTTP impl | `ze_core.openrouter.system_one` |
| Disabled impl | same module, `DisabledSystemOneClient` |

`SystemOneClient` is a sibling of `NLIClient` and `LLMClient`. It MUST NOT add methods to `LLMClient`. Plugin code MUST import from `ze_sdk` (or `ze_agents` in engine tests), never `ze_core`.

## Protocol

```python
@runtime_checkable
class SystemOneClient(Protocol):
    async def evaluate(
        self,
        state: str | dict,
        questions: dict[str, SystemOneQuestion],
    ) -> SystemOneResult: ...
```

- One HTTP round-trip per `evaluate` (all questions in the map).
- Fail-open: timeout, missing key, 429, 529, 5xx, and transport errors return `outcome="skip"`; they MUST NOT raise into the graph.
- Invalid payload (empty `questions`, empty `state`, bad `type`) returns skip `invalid_request` without a network call.
- `DisabledSystemOneClient.evaluate` returns skip `disabled` immediately.

## DI

- `build_engine_stack` constructs the live or disabled client from `settings.config["system_one"]` and `settings.openrouter_api_key`.
- `dep_map[SystemOneClient] = client`.
- `ZeContainer._build_config` sets `configurable["system_one_client"]`.
- Constructor injection only. No module-level mutable client.

## What 162 must not expose

- Agent `@tool` that forwards arbitrary session state.
- Chat-completions wrapper.
- Public REST “judge this text” endpoint.
