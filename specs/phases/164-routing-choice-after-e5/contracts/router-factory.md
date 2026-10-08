# Contract: One router factory

Home: `core/engine/ze-core/ze_core/routing/factory.py`.

```python
def router_config_from(config: dict) -> RouterConfig
def build_embedding_router(
    *,
    embedder,
    openrouter_client,
    config: dict,                 # settings.config
    system_one_client,
    routing_store=None,
    estimator=None,
) -> EmbeddingRouter
```

- `router_config_from` reads `routing.threshold` and `routing.gap_threshold` (defaults `ROUTING_THRESHOLD`, `ROUTING_GAP_THRESHOLD`) and `resolve_model("router_fallback", MODEL_ROUTER_FALLBACK, config)` for `fallback_model`.
- `build_embedding_router` passes `app_config=config` so `models.default`/`models.overrides` apply through `_resolve_model`, and builds `routing_surface_config(config)`.
- Both construction sites call it and nothing else constructs `EmbeddingRouter` outside tests:
  - `bootstrap.build_router(stack, settings)` (called by `ze_api/container.py`),
  - `Container.build` step 9 in `ze_core/container.py`, which now builds a `SystemOneClient` via `build_system_one_client(settings, cost_tracker=…)` and registers it in `deps`.
- Hard cut: the inline `RouterConfig(...)` blocks and the `RouterConfig()`-only `build_router` are deleted.

Tests: the YAML threshold, `models.overrides[<agent>]`, the `router_fallback` model and the injected client are visible on the router for both call sites.
