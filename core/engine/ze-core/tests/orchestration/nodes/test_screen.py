from ze_agents.interface.types import RawInput

from unittest.mock import AsyncMock, MagicMock

from ze_agents.screen import ResolveContext, ScreenContext, ScreenLine, ScreenRef
from ze_core.conversation.turn import make_graph_input
from ze_core.orchestration.judgment_state import build_judgment_state
from ze_core.orchestration.nodes.screen import resolve_screen
from ze_core.orchestration.state import AgentState
from ze_core.screen import ScreenResolverRegistry


class Goals:
    kinds = frozenset({"goal"})

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return [
            ScreenLine(
                ref=r, label="LedgerLite launch", summary="active, 2/5 milestones"
            )
            for r in refs
        ]


class Boom:
    kinds = frozenset({"goal"})

    async def resolve(self, refs, ctx):
        raise RuntimeError("down")


def _config(ctx=None, registry=None):
    return {"configurable": {"screen_context": ctx, "screen_resolvers": registry}}


CTX = ScreenContext(place="doing", subject=(ScreenRef(kind="goal", id="g1"),))


async def test_no_context_or_registry_gives_nothing():
    state = {"prompt": "hi", "session_id": "s"}
    assert await resolve_screen(state, _config()) == {}
    assert await resolve_screen(state, _config(CTX, None)) == {}
    assert (
        await resolve_screen(
            state, _config(ScreenContext(), ScreenResolverRegistry([Goals()]))
        )
        == {}
    )


async def test_context_gives_note_trace_and_subject_line():
    out = await resolve_screen({}, _config(CTX, ScreenResolverRegistry([Goals()])))
    assert "LedgerLite launch" in out["screen_note"]
    assert out["screen_subject_line"] == 'Screen subject: goal "LedgerLite launch"'
    assert out["screen_trace"]["resolvers"] == [
        {
            "kind": "goal",
            "id": "g1",
            "status": "ok",
            "ms": out["screen_trace"]["resolvers"][0]["ms"],
        }
    ]


async def test_a_raising_builder_gives_nothing(monkeypatch):
    from ze_core.orchestration.nodes import screen as node

    async def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(node, "build_screen_note", boom)
    assert (
        await resolve_screen({}, _config(CTX, ScreenResolverRegistry([Goals()]))) == {}
    )


async def test_a_raising_resolver_still_gives_a_note():
    out = await resolve_screen({}, _config(CTX, ScreenResolverRegistry([Boom()])))
    assert "Could not load goal." in out["screen_note"]


def test_make_graph_input_resets_the_screen_keys():
    graph_input = make_graph_input(RawInput(text="hi"), "s")
    assert graph_input["screen_note"] is None
    assert graph_input["screen_trace"] is None
    assert graph_input["screen_subject_line"] is None
    assert {"screen_note", "screen_trace", "screen_subject_line"} <= set(
        AgentState.__annotations__
    )


def test_judgment_state_is_unchanged_without_a_screen_line():
    state = {"prompt": "what about this?", "routing_hints": "goal hints"}
    assert build_judgment_state(state) == {
        "user": "what about this?",
        "context": "goal hints",
    }


def test_screen_line_is_appended_to_context_once_and_capped():
    state = {"prompt": "what about this?", "routing_hints": "goal hints"}
    out = build_judgment_state(state, 'Screen subject: goal "X"')
    assert out["context"] == 'goal hints\nScreen subject: goal "X"'
    long = build_judgment_state({"prompt": "p"}, "x" * 500)
    assert len(long["context"]) == 120
    full = build_judgment_state({"prompt": "p", "routing_hints": "h" * 900}, "line")
    assert full["context"].endswith("\nline") and len(full["context"]) <= 600


def test_routing_hints_are_not_modified_by_the_screen_line():
    state = {"prompt": "p", "routing_hints": "hints"}
    build_judgment_state(state, "line")
    assert state["routing_hints"] == "hints"


async def _routed_state(screen_hint: bool) -> dict:
    from ze_core.orchestration.nodes.routing import embed_route
    from ze_core.routing.types import RoutingEnvelope, SubTask

    envelope = RoutingEnvelope(
        primary_agent="companion",
        confidence=0.9,
        score_gap=0.5,
        routing_method="embedding",
        is_compound=False,
        subtasks=[SubTask(agent="companion", prompt="p")],
        requires_synthesis=False,
        raw_scores={"companion": 0.9},
    )
    router = MagicMock()
    router.screen_hint = screen_hint
    router.route = AsyncMock(return_value=envelope)
    state = {
        "session_id": "s",
        "prompt": "what about this?",
        "routing_hints": "hints",
        "screen_subject_line": 'Screen subject: goal "X"',
    }
    await embed_route(state, {"configurable": {"router": router}})
    return router.route.call_args.kwargs["judgment_state"]


async def test_routing_state_gets_the_screen_line_only_when_screen_hint_is_on():
    off = await _routed_state(False)
    on = await _routed_state(True)
    assert off["context"] == "hints"
    assert on["context"] == 'hints\nScreen subject: goal "X"'
