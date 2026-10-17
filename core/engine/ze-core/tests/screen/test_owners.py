import pytest
from ze_agents.screen import ScreenContext, ScreenOrigin, ScreenRef
from ze_core.screen.owners import OWNER_AGENT, screen_owner

ENABLED = {"companion", "loops", "goals", "workflow", "reminders", "news", "research"}


def ctx(kind, origin=ScreenOrigin.CHAT_ABOUT, subject=True):
    return ScreenContext(
        origin=origin, subject=(ScreenRef(kind=kind, id="x"),) if subject else ()
    )


@pytest.mark.parametrize(
    "kind,agent",
    [
        ("loop", "loops"),
        ("goal", "goals"),
        ("goal_gate", "goals"),
        ("workflow", "workflow"),
        ("workflow_execution", "workflow"),
        ("reminder", "reminders"),
        ("news_article", "news"),
        ("fact", "companion"),
        ("entity", "companion"),
        ("contact", "companion"),
        ("notification", "companion"),
        ("hypothesis", "companion"),
        ("never_heard_of_it", "companion"),
    ],
)
def test_subject_kind_picks_its_owner(kind, agent):
    assert screen_owner(ctx(kind), ENABLED) == agent


def test_typed_ask_bar_turns_route_as_usual():
    assert screen_owner(ctx("loop", origin=ScreenOrigin.ASK_BAR), ENABLED) is None


def test_no_subject_or_no_context_routes_as_usual():
    assert screen_owner(ctx("loop", subject=False), ENABLED) is None
    assert screen_owner(None, ENABLED) is None


def test_a_disabled_owner_falls_back_to_companion_or_nothing():
    assert screen_owner(ctx("loop"), ENABLED - {"loops"}) == "companion"
    assert screen_owner(ctx("loop"), {"research"}) is None


def test_every_mapped_owner_is_a_real_agent_name():
    assert set(OWNER_AGENT.values()) <= {
        "loops",
        "goals",
        "workflow",
        "reminders",
        "news",
    }
