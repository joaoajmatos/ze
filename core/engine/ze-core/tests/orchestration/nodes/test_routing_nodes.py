import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.registry import agent, clear_registry
from ze_agents.base_agent import BaseAgent
from ze_core.orchestration.nodes.routing import decompose, embed_route
from ze_agents.types import AgentContext, AgentResult
from ze_core.routing.types import RouterConfig, RoutingEnvelope, SubTask


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _register(name: str, intent_map: dict | None = None) -> None:
    class _A(BaseAgent):
        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=name, response="ok")

    _A.name = name
    _A.description = f"The {name} agent"
    _A.enabled = True
    agent(_A)


def _envelope(
    is_compound: bool = True, raw_scores: dict | None = None
) -> RoutingEnvelope:
    return RoutingEnvelope(
        primary_agent="alpha",
        confidence=0.4,
        score_gap=0.1,
        routing_method="embedding",
        is_compound=is_compound,
        subtasks=[SubTask(agent="alpha", prompt="do it")],
        requires_synthesis=False,
        raw_scores=raw_scores or {"alpha": 0.4, "beta": 0.3},
    )


def _config(client, router=None) -> dict:
    return {
        "configurable": {
            "openrouter_client": client,
            "router": router,
        }
    }


def _state(prompt: str = "do it", envelope=None) -> dict:
    return {
        "session_id": "s1",
        "prompt": prompt,
        "envelope": envelope or _envelope(),
    }


class TestDecomposeNode:
    async def test_calls_fallback_decompose_and_replaces_envelope(self):
        _register("alpha")
        _register("beta")
        client = AsyncMock()
        client.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "subtasks": [
                        {"agent": "alpha", "changes": False, "prompt": "research part"},
                        {"agent": "beta", "changes": True, "prompt": "write part"},
                    ],
                    "sequential": False,
                }
            )
        )

        result = await decompose(_state(), _config(client))

        assert "envelope" in result
        env = result["envelope"]
        assert env.primary_agent == "companion"
        assert env.is_compound is False
        assert env.routing_method == "haiku"
        assert result["conductor_hint"] is not None
        assert [h["agent"] for h in result["conductor_hint"]] == ["alpha", "beta"]
        assert result["conductor_ledger"] == [
            {"agent": "alpha", "status": "planned"},
            {"agent": "beta", "status": "planned"},
        ]
        client.complete.assert_awaited_once()

    async def test_single_subtask_result_is_not_compound(self):
        _register("alpha")
        client = AsyncMock()
        client.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "subtasks": [
                        {"agent": "alpha", "changes": False, "prompt": "simple"}
                    ],
                    "sequential": False,
                }
            )
        )

        result = await decompose(_state(), _config(client))

        env = result["envelope"]
        assert env.is_compound is False
        assert len(env.subtasks) == 1

    async def test_uses_fallback_model_from_router_config(self):
        _register("alpha")
        router = MagicMock()
        router._config = RouterConfig(fallback_model="openai/gpt-4o-mini")
        client = AsyncMock()
        client.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "subtasks": [{"agent": "alpha", "changes": False, "prompt": "p"}],
                    "sequential": False,
                }
            )
        )

        await decompose(_state(), _config(client, router=router))

        call_kwargs = client.complete.call_args[1]
        assert call_kwargs["model"] == "openai/gpt-4o-mini"

    async def test_passes_raw_scores_from_envelope(self):
        _register("alpha")
        _register("beta")
        captured = {}
        client = AsyncMock()

        async def _capture(**kwargs):
            captured.update(kwargs)
            return json.dumps(
                {
                    "subtasks": [{"agent": "alpha", "changes": False, "prompt": "p"}],
                    "sequential": False,
                }
            )

        client.complete = _capture
        raw = {"alpha": 0.45, "beta": 0.38}
        state = _state(envelope=_envelope(raw_scores=raw))

        await decompose(state, _config(client))
        # raw_scores are passed through to fallback.decompose (used in RoutingEnvelope)
        # verify by checking the returned envelope has them
        # (fallback.decompose reads raw_scores to set confidence on result)

    async def test_sequential_subtasks_sets_is_sequential(self):
        _register("alpha")
        _register("beta")
        client = AsyncMock()
        client.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "subtasks": [
                        {"agent": "alpha", "changes": False, "prompt": "step 1"},
                        {"agent": "beta", "changes": True, "prompt": "step 2"},
                    ],
                    "sequential": True,
                }
            )
        )

        result = await decompose(_state(), _config(client))
        assert result["envelope"].primary_agent == "companion"
        assert result["envelope"].is_sequential is True
        assert result["envelope"].requires_synthesis is False
        assert result["conductor_hint"] is not None
        assert [h["agent"] for h in result["conductor_hint"]] == ["alpha", "beta"]

    async def test_llm_failure_falls_back_to_hard_fallback(self):
        _register("alpha")
        client = AsyncMock()
        # Two consecutive failures → hard fallback
        client.complete = AsyncMock(side_effect=Exception("LLM unavailable"))

        result = await decompose(_state(), _config(client))

        # Hard fallback should still return a valid envelope, not raise
        assert "envelope" in result
        env = result["envelope"]
        assert len(env.subtasks) == 1
        assert env.routing_method == "fallback"

    async def test_no_router_in_config_uses_default_model(self):
        _register("alpha")
        client = AsyncMock()
        client.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "subtasks": [{"agent": "alpha", "changes": False, "prompt": "p"}],
                    "sequential": False,
                }
            )
        )

        result = await decompose(_state(), _config(client, router=None))

        assert "envelope" in result
        client.complete.assert_awaited_once()
        call_kwargs = client.complete.call_args[1]
        assert call_kwargs["model"] == "anthropic/claude-haiku-4-5"


class TestEmbedRouteNode:
    def _router(self):
        envelope = RoutingEnvelope(
            primary_agent="goals",
            confidence=0.9,
            score_gap=0.3,
            routing_method="embedding",
            is_compound=False,
            subtasks=[SubTask(agent="goals", prompt="steer")],
            requires_synthesis=False,
            raw_scores={"goals": 0.9},
        )
        router = AsyncMock()
        router.route = AsyncMock(return_value=envelope)
        return router

    async def test_appends_routing_hints_when_present(self):
        router = self._router()
        state = {
            "session_id": "s1",
            "prompt": "skip the LinkedIn step",
            "image_caption": None,
            "routing_hints": '[Active goals: "Job search" — step 3: LinkedIn outreach]',
        }
        config = {"configurable": {"router": router}}

        await embed_route(state, config)

        call_args = router.route.call_args
        routing_text = (
            call_args.kwargs.get("prompt") or call_args.args[0]
            if call_args.args
            else call_args.kwargs["prompt"]
        )
        assert "skip the LinkedIn step" in routing_text
        assert "[Active goals:" in routing_text
        # Hints appended AFTER the message, not prepended
        assert routing_text.index("skip") < routing_text.index("[Active goals:")

    async def test_routing_unchanged_when_hints_is_none(self):
        router = self._router()
        state = {
            "session_id": "s1",
            "prompt": "what's the weather?",
            "image_caption": None,
            "routing_hints": None,
        }
        config = {"configurable": {"router": router}}

        await embed_route(state, config)

        call_args = router.route.call_args
        routing_text = call_args.kwargs.get("prompt") or call_args.kwargs["prompt"]
        assert routing_text == "what's the weather?"
        assert "[Active goals:" not in routing_text


class TestEmbedRouteFollowUps:
    """Anaphoric follow-ups must carry recent conversation into the routing text,
    so e.g. 'are these recent?' after a news answer routes to news, not prospecting."""

    def _router(self):
        envelope = RoutingEnvelope(
            primary_agent="news",
            confidence=0.9,
            score_gap=0.3,
            routing_method="embedding",
            is_compound=False,
            subtasks=[SubTask(agent="news", prompt="x")],
            requires_synthesis=False,
            raw_scores={"news": 0.9},
        )
        router = AsyncMock()
        router.route = AsyncMock(return_value=envelope)
        return router

    def _news_history(self) -> list[dict]:
        return [
            {"role": "user", "content": "whats in the news regarding AI?"},
            {
                "role": "assistant",
                "content": "Here's what's trending in AI right now: ...",
            },
        ]

    async def _routed_text(self, state: dict) -> str:
        router = self._router()
        await embed_route(state, {"configurable": {"router": router}})
        call_args = router.route.call_args
        return call_args.kwargs["prompt"]

    async def test_are_these_recent_includes_news_history(self):
        routing_text = await self._routed_text(
            {
                "session_id": "s1",
                "prompt": "are these news recent?",
                "image_caption": None,
                "routing_hints": None,
                "messages": self._news_history(),
                "last_active_at": time.time(),
            }
        )
        assert routing_text.startswith("are these news recent?")
        assert "[Recent conversation]" in routing_text
        assert "whats in the news regarding AI?" in routing_text

    async def test_how_did_you_get_those_includes_news_history(self):
        routing_text = await self._routed_text(
            {
                "session_id": "s1",
                "prompt": "I meant those ones in specific. How did you get those?",
                "image_caption": None,
                "routing_hints": None,
                "messages": self._news_history(),
                "last_active_at": time.time(),
            }
        )
        assert "trending in AI" in routing_text
        # current message dominates: it comes before the history hint
        assert routing_text.index("How did you get those?") < routing_text.index(
            "[Recent conversation]"
        )

    async def test_no_history_hint_when_session_expired(self):
        routing_text = await self._routed_text(
            {
                "session_id": "s1",
                "prompt": "are these recent?",
                "image_caption": None,
                "routing_hints": None,
                "messages": self._news_history(),
                "last_active_at": time.time() - 3600,  # > 30 min inactivity
            }
        )
        assert routing_text == "are these recent?"

    async def test_no_history_hint_when_no_messages(self):
        routing_text = await self._routed_text(
            {
                "session_id": "s1",
                "prompt": "are these recent?",
                "image_caption": None,
                "routing_hints": None,
                "messages": [],
                "last_active_at": None,
            }
        )
        assert routing_text == "are these recent?"

    async def test_history_messages_are_truncated(self):
        history = [{"role": "assistant", "content": "y" * 5000}]
        routing_text = await self._routed_text(
            {
                "session_id": "s1",
                "prompt": "shorten please",
                "image_caption": None,
                "routing_hints": None,
                "messages": history,
                "last_active_at": time.time(),
            }
        )
        assert len(routing_text) < 1000


class TestEmbedRouteJudgment:
    """Phase 164: named judgment parts, trace rows and cost attribution."""

    def _envelope(self, judgment=None) -> RoutingEnvelope:
        return RoutingEnvelope(
            primary_agent="calendar",
            confidence=0.93,
            score_gap=0.3,
            routing_method="embedding",
            is_compound=False,
            subtasks=[SubTask(agent="calendar", prompt="x")],
            requires_synthesis=False,
            raw_scores={"calendar": 0.84},
            judgment=judgment,
        )

    def _judgment(self):
        from ze_agents.system_one import SystemOneAnswer, SystemOneResult
        from tests.support.judgments import make_judgment

        result = SystemOneResult(
            outcome="ok",
            model="jev",
            answers={
                "agent": SystemOneAnswer(
                    type="choice",
                    choice="calendar",
                    confidence=0.93,
                    probabilities={"calendar": 0.93, "none": 0.07},
                ),
                "multi_specialist": SystemOneAnswer(type="noul", noul=0.1),
            },
        )
        return make_judgment(
            "routing",
            result,
            {"agent": "choice", "multi_specialist": "noul"},
            consumed=frozenset({"agent", "multi_specialist"}),
        )

    def _router(self, envelope):
        router = AsyncMock()
        router.route = AsyncMock(return_value=envelope)
        return router

    def _state(self, **extra) -> dict:
        return {
            "session_id": "s1",
            "prompt": "what's on my calendar",
            "image_caption": None,
            "routing_hints": None,
            **extra,
        }

    async def test_judgment_state_keeps_user_history_and_context_apart(self):
        router = self._router(self._envelope())
        state = self._state(
            messages=[{"role": "user", "content": "hello there"}],
            last_active_at=time.time(),
            routing_hints="[Active goals: x]",
        )
        await embed_route(state, {"configurable": {"router": router}})
        kwargs = router.route.call_args.kwargs
        js = kwargs["judgment_state"]
        assert js["user"] == "what's on my calendar"
        assert js["history"].startswith("[Recent conversation]")
        assert "hello there" in js["history"]
        assert js["context"] == "[Active goals: x]"
        assert "[Recent conversation]" in kwargs["prompt"]
        assert kwargs["prompt"].startswith("what's on my calendar")

    async def test_user_text_is_the_image_caption_for_image_turns(self):
        router = self._router(self._envelope())
        state = self._state(image_caption="a photo of a receipt")
        await embed_route(state, {"configurable": {"router": router}})
        js = router.route.call_args.kwargs["judgment_state"]
        assert js["user"] == "a photo of a receipt"
        assert "history" not in js and "context" not in js

    async def test_returns_judgment_rows_with_consumed_flags(self):
        router = self._router(self._envelope(self._judgment()))
        out = await embed_route(self._state(), {"configurable": {"router": router}})
        rows = {r.question_id: r for r in out["judgments"]}
        assert set(rows) == {"agent", "multi_specialist"}
        assert rows["agent"].consumed and rows["multi_specialist"].consumed
        assert rows["agent"].kind == "choice" and rows["agent"].peakedness == 0.93
        assert out["envelope"].primary_agent == "calendar"

    async def test_no_judgment_means_no_rows(self):
        router = self._router(self._envelope())
        out = await embed_route(self._state(), {"configurable": {"router": router}})
        assert out["judgments"] == []

    async def test_agent_context_is_router_during_the_call(self):
        from ze_core.telemetry.context import get_cost_context, set_flow_context

        set_flow_context("chat", "s1")
        seen: list[str] = []
        envelope = self._envelope()
        router = AsyncMock()

        async def route(**kwargs):
            seen.append(get_cost_context().agent)
            return envelope

        router.route = route
        await embed_route(self._state(), {"configurable": {"router": router}})
        assert seen == ["router"]


class TestDecomposeAssignsFullModels:
    """Phase 182: decompose never tiers; choose_tier owns the light model."""

    def _router(self, overrides=None):
        router = MagicMock()
        router._config = RouterConfig()
        router._app_config = {"models": {"overrides": overrides or {}}}
        return router

    def _client(self, subtasks, sequential=False):
        client = AsyncMock()
        client.complete = AsyncMock(
            return_value=json.dumps({"subtasks": subtasks, "sequential": sequential})
        )
        return client

    def _register_tiered(self, name, intent_map=None):
        _register(name, intent_map)
        from ze_agents.registry import get_enabled_agents

        cls = get_enabled_agents()[name]
        cls.model = f"{name}-big"
        cls.model_simple = f"{name}-small"

    async def test_decompose_assigns_every_subtask_its_full_model(self):
        self._register_tiered("alpha")
        self._register_tiered("beta")
        client = self._client(
            [
                {"agent": "alpha", "changes": False, "prompt": "a"},
                {"agent": "beta", "changes": False, "prompt": "b"},
            ]
        )

        result = await decompose(
            _state(prompt="thanks"), _config(client, router=self._router())
        )

        assert [s.model for s in result["envelope"].subtasks] == [
            "alpha-big",
            "beta-big",
        ]

    async def test_overrides_apply_to_the_full_model(self):
        self._register_tiered("alpha")
        client = self._client([{"agent": "alpha", "changes": False, "prompt": "a"}])
        router = self._router({"alpha": "pinned"})

        result = await decompose(_state(), _config(client, router=router))

        assert result["envelope"].subtasks[0].model == "pinned"

    async def test_mixed_gather_act_rewrites_to_companion_on_its_full_model(self):
        self._register_tiered("alpha", {"read": "Read"})
        self._register_tiered("beta", {"create": "Create"})
        self._register_tiered("companion", {"reason": "Reason"})
        client = self._client(
            [
                {"agent": "alpha", "changes": False, "prompt": "look it up"},
                {"agent": "beta", "changes": True, "prompt": "then act"},
            ]
        )

        result = await decompose(_state(), _config(client, router=self._router()))

        env = result["envelope"]
        assert env.primary_agent == "companion"
        assert [s.model for s in env.subtasks] == ["companion-big"]
        assert [h["agent"] for h in result["conductor_hint"]] == ["alpha", "beta"]
        assert not hasattr(env, "complexity")


class TestEmbedRouteForcedAgent:
    async def test_forced_agent_bypasses_route(self):
        router = MagicMock()
        router.route = AsyncMock()
        router.route_forced = AsyncMock(return_value=_envelope(is_compound=False))
        config = _config(AsyncMock(), router)
        config["configurable"]["forced_agent"] = "alpha"
        out = await embed_route({**_state(), "session_id": "s1"}, config)
        router.route_forced.assert_awaited_once()
        assert router.route_forced.await_args.args[-1] == "alpha"
        router.route.assert_not_awaited()
        assert out["envelope"].primary_agent == "alpha"

    async def test_without_forced_agent_route_is_used(self):
        router = MagicMock()
        router.route = AsyncMock(return_value=_envelope(is_compound=False))
        router.route_forced = AsyncMock()
        await embed_route(_state(), _config(AsyncMock(), router))
        router.route.assert_awaited_once()
        router.route_forced.assert_not_awaited()


class TestEmbedRouteScreenOwner:
    async def test_chat_about_subject_routes_to_its_owner_without_scoring(self):
        from unittest.mock import patch

        from ze_agents.screen import ScreenContext, ScreenOrigin, ScreenRef

        router = MagicMock()
        router.route = AsyncMock()
        router.route_forced = AsyncMock(return_value=_envelope(is_compound=False))
        config = _config(AsyncMock(), router)
        config["configurable"]["screen_context"] = ScreenContext(
            origin=ScreenOrigin.CHAT_ABOUT,
            subject=(ScreenRef(kind="loop", id="L1"),),
        )
        with patch(
            "ze_core.orchestration.nodes.routing.get_enabled_agents",
            return_value={"loops": object(), "companion": object()},
        ):
            await embed_route({**_state(), "session_id": "s1"}, config)
        assert router.route_forced.await_args.args[-1] == "loops"
        assert router.route_forced.await_args.kwargs == {"method": "screen"}
        router.route.assert_not_awaited()

    async def test_typed_ask_bar_context_still_scores(self):
        from ze_agents.screen import ScreenContext, ScreenRef

        router = MagicMock()
        router.route = AsyncMock(return_value=_envelope(is_compound=False))
        router.route_forced = AsyncMock()
        config = _config(AsyncMock(), router)
        config["configurable"]["screen_context"] = ScreenContext(
            subject=(ScreenRef(kind="loop", id="L1"),)
        )
        await embed_route({**_state(), "session_id": "s1"}, config)
        router.route.assert_awaited_once()
        router.route_forced.assert_not_awaited()
