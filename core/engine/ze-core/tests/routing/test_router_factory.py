"""One router factory — YAML, overrides, fallback and client reach the router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ze_agents.defaults import (
    MODEL_ROUTER_FALLBACK,
    ROUTING_GAP_THRESHOLD,
    ROUTING_THRESHOLD,
)
from ze_agents.registry import clear_registry
from ze_core.routing.factory import build_embedding_router, router_config_from
from ze_core.routing.judge import RoutingSurfaceConfig
from tests.support.routing import FakeSystemOneClient, cosine_embedder, register_agent


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _build(config: dict, client=None):
    register_agent("alpha", model="alpha-big", model_simple="alpha-small")
    register_agent("beta")
    system_one = client or FakeSystemOneClient()
    router = build_embedding_router(
        embedder=cosine_embedder({"alpha": 0.9, "beta": 0.2}),
        openrouter_client=AsyncMock(),
        config=config,
        system_one_client=system_one,
    )
    return router, system_one


class TestRouterConfigFrom:
    def test_defaults_when_routing_block_absent(self):
        cfg = router_config_from({})
        assert cfg.threshold == ROUTING_THRESHOLD
        assert cfg.gap_threshold == ROUTING_GAP_THRESHOLD
        assert cfg.fallback_model == MODEL_ROUTER_FALLBACK

    def test_yaml_threshold_and_gap(self):
        cfg = router_config_from(
            {"routing": {"threshold": 0.61, "gap_threshold": 0.05}}
        )
        assert (cfg.threshold, cfg.gap_threshold) == (0.61, 0.05)

    def test_router_fallback_override(self):
        cfg = router_config_from({"models": {"overrides": {"router_fallback": "x/y"}}})
        assert cfg.fallback_model == "x/y"


class TestBuildEmbeddingRouter:
    def test_yaml_threshold_reaches_router(self):
        router, _ = _build({"routing": {"threshold": 0.5, "gap_threshold": 0.1}})
        assert router._config.threshold == 0.5
        assert router._config.gap_threshold == 0.1

    def test_models_overrides_change_resolved_model(self):
        router, _ = _build({"models": {"overrides": {"alpha": "override/alpha"}}})
        assert router._resolve_model("alpha", "complex") == "override/alpha"
        assert router._resolve_model("beta", "complex") == "m"

    def test_router_fallback_model_reaches_router(self):
        router, _ = _build({"models": {"overrides": {"router_fallback": "x/y"}}})
        assert router._config.fallback_model == "x/y"

    def test_client_and_surface_are_on_the_router(self):
        client = FakeSystemOneClient()
        config = {
            "system_one": {
                "surfaces": {
                    "routing": {
                        "enabled": True,
                        "choice_trust": 0.8,
                        "multi_specialist_hold": 0.6,
                    }
                }
            }
        }
        router, _ = _build(config, client=client)
        assert router._system_one is client
        assert router._surface.calibrated

    def test_surface_off_by_default(self):
        router, _ = _build({})
        assert router._surface == RoutingSurfaceConfig()


class TestCallSites:
    def test_bootstrap_build_router_uses_factory(self):
        from ze_core import bootstrap

        stack = SimpleNamespace(
            embedder=MagicMock(),
            openrouter_client=MagicMock(),
            pool=MagicMock(),
            estimator=MagicMock(),
            system_one_client=FakeSystemOneClient(),
        )
        settings = SimpleNamespace(config={"routing": {"threshold": 0.4}})
        with patch.object(bootstrap, "build_embedding_router") as factory:
            router = bootstrap.build_router(stack, settings)
        factory.assert_called_once()
        kwargs = factory.call_args.kwargs
        assert router is factory.return_value
        assert kwargs["config"] is settings.config
        assert kwargs["system_one_client"] is stack.system_one_client
        assert kwargs["embedder"] is stack.embedder
        assert kwargs["estimator"] is stack.estimator

    def test_base_container_step_uses_factory(self):
        from ze_core import container

        client = FakeSystemOneClient()
        settings = SimpleNamespace(config={"routing": {"threshold": 0.4}})
        with patch.object(container, "build_embedding_router") as factory:
            router = container._build_router(
                settings=settings,
                embedder=MagicMock(),
                openrouter_client=MagicMock(),
                pool=None,
                system_one_client=client,
            )
        factory.assert_called_once()
        kwargs = factory.call_args.kwargs
        assert router is factory.return_value
        assert kwargs["config"] is settings.config
        assert kwargs["system_one_client"] is client
        assert kwargs["routing_store"] is None
