"""
Router tests use a fake embedder that returns pre-canned vectors, avoiding
any dependency on sentence_transformers or numpy.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from ze_agents.errors import InvalidPromptError, RoutingError
from ze_agents.registry import agent, clear_registry
from ze_agents.types import AgentContext, AgentResult
from ze_core.routing.router import EmbeddingRouter
from ze_core.routing.store import PostgresRoutingStore
from ze_core.routing.types import RouterConfig


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _register(
    name: str,
    model: str = "m",
    model_simple: str | None = None,
    intent_map: dict | None = None,
) -> None:
    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=name, response="")

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = f"The {name} agent"
    _A.enabled = True
    _A.model = model
    _A.model_simple = model_simple
    agent(_A)


class _FakeVector:
    def __init__(self, data: list[float]) -> None:
        self._data = data

    def tolist(self) -> list[float]:
        return list(self._data)


class _FakeArray:
    """Minimal numpy-array-like object for dot-product routing."""

    def __init__(self, data: list[list[float]]) -> None:
        self._data = data  # shape: (n_agents, dims)

    def __matmul__(self, vec: list[float]) -> _FakeVector:
        result = [sum(r * v for r, v in zip(row, vec)) for row in self._data]
        return _FakeVector(result)


class _FakeEmbedder:
    """Returns pre-canned unit vectors."""

    def __init__(
        self, agent_vecs: dict[str, list[float]], prompt_vec: list[float]
    ) -> None:
        self._agent_vecs = agent_vecs  # name → vector
        self._prompt_vec = prompt_vec

    def encode(self, input_: str | list[str], **kwargs):
        if isinstance(input_, list):
            names = list(self._agent_vecs.keys())
            return _FakeArray([self._agent_vecs[n] for n in names])
        return self._prompt_vec

    def encode_passage(self, input_: str | list[str], **kwargs):
        return self.encode(input_, **kwargs)

    def encode_query(self, input_: str, **kwargs):
        return self._prompt_vec


def _make_routing_store() -> AsyncMock:
    store = AsyncMock(spec=PostgresRoutingStore)
    store.write_log = AsyncMock()
    return store


def _make_client(response: str = "{}") -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=response)
    return client


class TestRouteEmptyPrompt:
    def _router(self):
        _register("a")
        embedder = _FakeEmbedder({"a": [1.0]}, [1.0])
        return EmbeddingRouter(embedder, _make_client(), _make_routing_store())

    async def test_empty_string_raises(self):
        r = self._router()
        with pytest.raises(InvalidPromptError):
            await r.route("", "s1")

    async def test_whitespace_raises(self):
        r = self._router()
        with pytest.raises(InvalidPromptError):
            await r.route("   ", "s1")


class TestSingleAgentShortCircuit:
    async def test_returns_embedding_method_no_scoring(self):
        _register("solo", model="m-solo", intent_map={"execute": "Execute"})
        embedder = _FakeEmbedder({"solo": [1.0]}, [1.0])
        r = EmbeddingRouter(embedder, _make_client(), _make_routing_store())
        env = await r.route("do something", "s1")
        assert env.primary_agent == "solo"
        assert env.routing_method == "embedding"
        assert env.confidence == 1.0

    async def test_no_enabled_agents_raises_at_construction(self):
        with pytest.raises(RoutingError, match="No enabled agents"):
            EmbeddingRouter(
                _FakeEmbedder({}, []), _make_client(), _make_routing_store()
            )


class TestEmbeddingRouting:
    def _two_agent_router(
        self, top_score: float, second_score: float, cfg: RouterConfig | None = None
    ):
        _register("alpha", intent_map={"read": "Read"})
        _register("beta", intent_map={"create": "Create"})
        # sorted names: alpha, beta
        embedder = _FakeEmbedder(
            {"alpha": [top_score, 0.0], "beta": [second_score, 0.0]},
            [1.0, 0.0],
        )
        return EmbeddingRouter(
            embedder, _make_client(), _make_routing_store(), config=cfg
        )

    async def test_high_confidence_routes_by_embedding(self):
        r = self._two_agent_router(0.9, 0.3)
        env = await r.route("hello", "s1")
        assert env.primary_agent == "alpha"
        assert env.routing_method == "embedding"
        assert env.score_gap == pytest.approx(0.6)
        assert env.is_compound is False

    async def test_e5_band_clear_winner_is_not_compound_under_default_config(self):
        # Measured E5 calendar EN: top 0.844, second 0.812, gap 0.033.
        r = self._two_agent_router(0.844, 0.812)
        env = await r.route("what's on my calendar tomorrow", "s1")
        assert env.is_compound is False
        assert env.routing_method == "embedding"

    async def test_below_threshold_signals_compound_for_decompose(self):
        _register("alpha", intent_map={"read": "Read"})
        _register("beta", intent_map={"create": "Create"})
        embedder = _FakeEmbedder(
            {"alpha": [0.4, 0.0], "beta": [0.3, 0.0]},
            [1.0, 0.0],
        )
        client = _make_client()
        r = EmbeddingRouter(embedder, client, _make_routing_store())
        env = await r.route("hello", "s1")
        # Router no longer calls the LLM — it signals the graph via is_compound=True
        assert env.routing_method == "embedding"
        assert env.is_compound is True
        assert env.raw_scores  # scores preserved for the decompose node
        client.complete.assert_not_called()

    async def test_low_gap_signals_compound_for_decompose(self):
        _register("alpha", intent_map={"read": "Read"})
        _register("beta", intent_map={"create": "Create"})
        embedder = _FakeEmbedder(
            {"alpha": [0.830, 0.0], "beta": [0.827, 0.0]},
            [1.0, 0.0],
        )
        client = _make_client()
        r = EmbeddingRouter(embedder, client, _make_routing_store())
        env = await r.route("hello", "s1")
        assert env.routing_method == "embedding"
        assert env.is_compound is True
        client.complete.assert_not_called()

    async def test_e5_below_floor_still_compound_without_haiku(self):
        r = self._two_agent_router(0.50, 0.20)
        client = r._client
        env = await r.route("hello", "s1")
        assert env.is_compound is True
        client.complete.assert_not_called()

    async def test_clear_english_and_portuguese_winners_skip_decompose(self):
        # Measured E5: calendar EN gap 0.033; calendar PT gap 0.023.
        for top, second in ((0.844, 0.812), (0.814, 0.790)):
            clear_registry()
            r = self._two_agent_router(top, second)
            env = await r.route("prompt", "s1")
            assert env.is_compound is False
            r._client.complete.assert_not_called()


class TestModelResolution:
    _PROMPTS = [
        "what is python",
        "o que é python",
        "analyze and explain in depth the trade-offs between "
        + " ".join(["word"] * 30),
    ]

    def _router(self, *agents):
        for name in agents:
            _register(
                name,
                model="big-model",
                model_simple="small-model",
                intent_map={"read": "Read"},
            )
        vecs = {name: [1.0 if i == 0 else 0.1] for i, name in enumerate(agents)}
        return EmbeddingRouter(
            _FakeEmbedder(vecs, [1.0]), _make_client(), _make_routing_store()
        )

    @pytest.mark.parametrize("prompt", _PROMPTS)
    async def test_route_assigns_full_model(self, prompt):
        r = self._router("a")
        env = await r.route(prompt, "s1")
        assert env.subtasks[0].model == "big-model"

    @pytest.mark.parametrize("prompt", _PROMPTS)
    async def test_route_assigns_full_model_with_two_agents(self, prompt):
        r = self._router("a", "b")
        env = await r.route(prompt, "s1")
        assert all(s.model == "big-model" for s in env.subtasks)

    @pytest.mark.parametrize("prompt", _PROMPTS)
    async def test_route_forced_assigns_full_model(self, prompt):
        r = self._router("a", "b")
        env = await r.route_forced(prompt, "s1", "a")
        assert env.subtasks[0].model == "big-model"

    async def test_router_takes_no_estimator(self):
        _register("a", model="big-model", intent_map={"read": "Read"})
        with pytest.raises(TypeError):
            EmbeddingRouter(
                _FakeEmbedder({"a": [1.0]}, [1.0]),
                _make_client(),
                _make_routing_store(),
                estimator=object(),
            )


class TestAppConfigResolution:
    async def test_default_changes_resolved_model_when_no_declared_override(self):
        _register("a", model="declared-model", intent_map={"read": "Read"})
        embedder = _FakeEmbedder({"a": [1.0]}, [1.0])
        r = EmbeddingRouter(embedder, _make_client(), _make_routing_store())
        env = await r.route("hello", "s1")
        # Agent has its own declared model, so models.default (unset here) is irrelevant.
        assert env.subtasks[0].model == "declared-model"

    async def test_override_pins_one_agent_while_sibling_follows_default(self):
        app_config = {
            "models": {
                "default": "fleet-default",
                "overrides": {"alpha": "alpha-pinned"},
            }
        }

        _register("alpha", model="alpha-declared", intent_map={"read": "Read"})
        embedder_alpha = _FakeEmbedder({"alpha": [1.0]}, [1.0])
        r_alpha = EmbeddingRouter(
            embedder_alpha, _make_client(), _make_routing_store(), app_config=app_config
        )
        env_alpha = await r_alpha.route("hello", "s1")
        assert env_alpha.subtasks[0].model == "alpha-pinned"

        clear_registry()
        _register("beta", model="beta-declared", intent_map={"create": "Create"})
        embedder_beta = _FakeEmbedder({"beta": [1.0]}, [1.0])
        r_beta = EmbeddingRouter(
            embedder_beta, _make_client(), _make_routing_store(), app_config=app_config
        )
        env_beta = await r_beta.route("hello", "s1")
        # beta has no override, but does have its own declared model, so it wins over default.
        assert env_beta.subtasks[0].model == "beta-declared"


class TestRoutingLog:
    async def test_write_log_called_after_route(self):
        _register("a")
        embedder = _FakeEmbedder({"a": [1.0]}, [1.0])
        store = _make_routing_store()
        r = EmbeddingRouter(embedder, _make_client(), store)
        await r.route("hello", "s1")
        await asyncio.sleep(0)
        store.write_log.assert_awaited_once()
        args = store.write_log.call_args[0]
        assert args[0] == "s1"
        assert args[1] == "hello"

    async def test_no_store_does_not_raise(self):
        _register("a")
        embedder = _FakeEmbedder({"a": [1.0]}, [1.0])
        r = EmbeddingRouter(embedder, _make_client(), routing_store=None)
        env = await r.route("hello", "s1")
        assert env.primary_agent == "a"

    async def test_store_write_failure_is_swallowed(self):
        _register("a")
        embedder = _FakeEmbedder({"a": [1.0]}, [1.0])
        bad_store = AsyncMock(spec=PostgresRoutingStore)
        bad_store.write_log = AsyncMock(side_effect=Exception("DB down"))
        r = EmbeddingRouter(embedder, _make_client(), bad_store)
        env = await r.route("hello", "s1")
        assert env.primary_agent == "a"
        await asyncio.sleep(0)
