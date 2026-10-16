"""build_tier_state — the capped, named task state the tier judge sees (research R3)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ze_agents.registry import clear_registry, get_enabled_agents
from ze_agents.types import AgentContext
from ze_core.orchestration.judgment_state import build_tier_state
from ze_core.routing.types import RoutingEnvelope, SubTask
from tests.support.routing import register_agent

FIELDS = {"task", "conversation", "recap", "memory", "focus", "skill"}

RECAP = (
    "[Resuming after a gap — outstanding context, not visible to the user]\n"
    "Last session: planned the Lisbon trip\n"
    "Still open:\n- book flights\n"
    "In-flight workflows:\n- Weekly digest (step 2 of 4)\n"
    "Not yet tracked (Ze noticed these; the user has not confirmed them):\n"
    "- renew passport\n"
    "End your reply with one short question, in the user's language, asking "
    "whether they want you to keep track of these."
)


@pytest.fixture(autouse=True)
def registry():
    clear_registry()
    register_agent("companion", description="Personal companion")
    get_enabled_agents()["companion"].tools = ["remember_fact", "track_loop"]
    yield
    clear_registry()


def _envelope(agent: str = "companion") -> RoutingEnvelope:
    return RoutingEnvelope(
        primary_agent=agent,
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=False,
        subtasks=[SubTask(agent=agent, intent="read", prompt="x", model="m")],
        requires_synthesis=False,
    )


def _messages(count: int) -> list[dict]:
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
        for i in range(count)
    ]


def _memory(facts: int, episodes: int) -> SimpleNamespace:
    return SimpleNamespace(
        facts=[
            SimpleNamespace(
                predicate=f"fact{i}",
                value="v" * 400,
                relevance_score=1.0 - i / 100,
                confidence=0.9,
            )
            for i in range(facts)
        ],
        episodes=[
            SimpleNamespace(summary=f"episode {i}", relevance_score=0.5)
            for i in range(episodes)
        ],
    )


def _full_state() -> dict:
    prior = _messages(9)
    ctx = AgentContext(
        session_id="s1",
        prompt="ok go ahead with that plan",
        intent="reason",
        messages=[*prior, {"role": "user", "content": "ok go ahead with that plan"}],
        resume_recap=RECAP,
        screen_context_note="The user is viewing workflow execution 42",
        procedure_matches=[SimpleNamespace(name="Weekly review")],
        active_skills=[
            SimpleNamespace(name="trip-planner", description="Plans trips"),
            SimpleNamespace(name="budget", description="Tracks budgets"),
        ],
    )
    return {
        "prompt": "ok go ahead with that plan",
        "image_caption": None,
        "agent_context": ctx,
        "memory_context": _memory(4, 3),
        "envelope": _envelope(),
        "routing_hints": "[Active goals: Ship v1 (milestone 2); Learn Portuguese]",
    }


class TestFields:
    def test_exact_field_names(self):
        assert set(build_tier_state(_full_state())) == FIELDS

    def test_task_is_the_prompt(self):
        assert build_tier_state(_full_state())["task"] == "ok go ahead with that plan"

    def test_image_turn_uses_the_caption(self):
        state = _full_state()
        state["image_caption"] = "a photo of a boarding pass"
        assert build_tier_state(state)["task"] == "a photo of a boarding pass"

    def test_empty_fields_are_omitted(self):
        state = {"prompt": "thanks", "image_caption": None}
        assert build_tier_state(state) == {"task": "thanks"}

    def test_skill_field_names_and_describes_active_skills(self):
        text = build_tier_state(_full_state())["skill"]
        assert "trip-planner" in text and "Plans trips" in text
        assert "budget" in text

    def test_focus_gathers_goals_screen_procedures_and_workflows(self):
        text = build_tier_state(_full_state())["focus"]
        assert "Active goals" in text
        assert "workflow execution 42" in text
        assert "Weekly review" in text
        assert "Weekly digest" in text

    def test_recap_keeps_the_narrative_without_chrome_or_offers(self):
        text = build_tier_state(_full_state())["recap"]
        assert "Lisbon trip" in text and "book flights" in text
        assert "Resuming after a gap" not in text
        assert "Weekly digest" not in text
        assert "renew passport" not in text
        assert "End your reply" not in text

    def test_no_routing_suffix_text_anywhere(self):
        state = build_tier_state(_full_state())
        assert not any("background only" in value for value in state.values())


class TestConversation:
    def test_last_eight_prior_messages_oldest_dropped_current_not_duplicated(self):
        text = build_tier_state(_full_state())["conversation"]
        lines = text.splitlines()
        assert len(lines) == 8
        assert lines[0] == "assistant: message 1"
        assert lines[-1] == "user: message 8"
        assert "message 0" not in text
        assert "go ahead" not in text

    def test_each_message_is_capped_at_400_chars(self):
        state = _full_state()
        state["agent_context"].messages = [
            {"role": "assistant", "content": "x" * 900},
            {"role": "user", "content": "now"},
        ]
        line = build_tier_state(state)["conversation"]
        assert line == "assistant: " + "x" * 400

    def test_total_is_capped_at_2400_dropping_the_oldest(self):
        state = _full_state()
        state["agent_context"].messages = [
            *[{"role": "assistant", "content": f"{i}" * 400} for i in range(8)],
            {"role": "user", "content": "now"},
        ]
        text = build_tier_state(state)["conversation"]
        assert len(text) <= 2400
        assert text.splitlines()[-1].startswith("assistant: 7")
        assert "assistant: 0" not in text

    def test_a_lone_current_message_leaves_no_conversation(self):
        state = _full_state()
        state["agent_context"].messages = [
            {"role": "user", "content": "ok go ahead with that plan"}
        ]
        assert "conversation" not in build_tier_state(state)

    def test_planning_exchange_reaches_the_judge(self):
        state = _full_state()
        state["agent_context"].messages = [
            {"role": "user", "content": "plan my week around the Lisbon trip"},
            {"role": "assistant", "content": "Mon: pack. Tue: flights. Wed: hotel."},
            {"role": "user", "content": "ok go ahead with that plan"},
        ]
        text = build_tier_state(state)["conversation"]
        assert "plan my week" in text and "Tue: flights" in text


class TestCaps:
    def test_task_capped_at_2000(self):
        state = _full_state()
        state["prompt"] = "p" * 5000
        assert len(build_tier_state(state)["task"]) == 2000

    def test_memory_is_top_five_items_of_at_most_200_chars(self):
        lines = build_tier_state(_full_state())["memory"].splitlines()
        assert len(lines) == 5
        assert all(len(line) <= 200 + 2 for line in lines)
        assert lines[0].startswith("- fact0")

    def test_recap_capped_at_800(self):
        state = _full_state()
        state["agent_context"].resume_recap = "Last session: " + "r" * 3000
        assert len(build_tier_state(state)["recap"]) == 800

    def test_focus_capped_at_600(self):
        state = _full_state()
        state["routing_hints"] = "g" * 3000
        assert len(build_tier_state(state)["focus"]) == 600

    def test_skill_capped_at_300(self):
        state = _full_state()
        state["agent_context"].active_skills = [
            SimpleNamespace(name=f"skill{i}", description="d" * 200) for i in range(5)
        ]
        assert len(build_tier_state(state)["skill"]) == 300

    def test_no_agent_field_and_no_routing_text(self):
        """Tuned-set figures (research R12): an agent field added noise to the difficulty judgment."""
        cls = get_enabled_agents()["companion"]
        cls.routing_criteria = "Not for: a comparison, a how-to"
        state = build_tier_state(_full_state())
        assert "agent" not in state
        assert not any("comparison" in value for value in state.values())
        assert not any("remember_fact" in value for value in state.values())

    def test_state_does_not_need_the_agent_registry(self):
        clear_registry()
        state = build_tier_state(_full_state())
        assert set(state) == FIELDS

    def test_whole_state_stays_under_eight_kilobytes(self):
        state = _full_state()
        state["prompt"] = "p" * 5000
        state["agent_context"].messages = [
            *[{"role": "assistant", "content": "c" * 900} for _ in range(9)],
            {"role": "user", "content": "now"},
        ]
        state["agent_context"].resume_recap = "Last session: " + "r" * 3000
        state["routing_hints"] = "g" * 3000
        total = sum(len(v) for v in build_tier_state(state).values())
        assert total < 8000
