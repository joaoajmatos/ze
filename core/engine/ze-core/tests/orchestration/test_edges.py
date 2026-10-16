from ze_core.orchestration.edges import (
    after_await_budget_confirmation,
    after_preflight,
    after_correlate,
    after_decompose,
    after_embed_route,
    after_execute_tool,
)
from ze_core.routing.types import RoutingEnvelope, SubTask


def make_envelope(
    is_compound: bool = False, agents=("research",), is_sequential: bool = False
) -> RoutingEnvelope:
    subtasks = [SubTask(agent=a, prompt="hi") for a in agents]
    return RoutingEnvelope(
        primary_agent=subtasks[0].agent,
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=is_compound,
        subtasks=subtasks,
        requires_synthesis=is_compound and not is_sequential,
        is_sequential=is_sequential,
    )


def base_state(**overrides) -> dict:
    defaults: dict = {
        "prompt": "hello",
        "session_id": "s1",
        "envelope": None,
        "memory_context": None,
        "agent_context": None,
        "agent_result": None,
        "subtask_results": [],
        "final_response": None,
        "error": None,
    }
    defaults.update(overrides)
    return defaults


# ── after_embed_route ─────────────────────────────────────────────────────────


def test_after_embed_route_single_goes_to_fetch_context():
    state = base_state(envelope=make_envelope(is_compound=False))
    assert after_embed_route(state) == "fetch_context"


def test_after_embed_route_compound_goes_to_decompose():
    state = base_state(
        envelope=make_envelope(is_compound=True, agents=("research", "companion"))
    )
    assert after_embed_route(state) == "decompose"


def test_after_embed_route_none_envelope_goes_to_fetch_context():
    state = base_state(envelope=None)
    assert after_embed_route(state) == "fetch_context"


def test_after_embed_route_sequential_compound_still_goes_to_decompose():
    state = base_state(
        envelope=make_envelope(
            is_compound=True, agents=("research", "email"), is_sequential=True
        )
    )
    assert after_embed_route(state) == "decompose"


def test_after_decompose_always_goes_to_fetch_context():
    state = base_state(
        envelope=make_envelope(
            is_compound=True, agents=("research", "email"), is_sequential=True
        )
    )
    assert after_decompose(state) == "fetch_context"


def test_after_decompose_non_sequential_goes_to_fetch_context():
    state = base_state(
        envelope=make_envelope(is_compound=True, agents=("research", "email"))
    )
    assert after_decompose(state) == "fetch_context"


# ── after_preflight ───────────────────────────────────────────────────────────


def test_after_preflight_runs_by_default():
    assert after_preflight(base_state()) == "execute_tool"


def test_after_preflight_blocked_ends():
    assert after_preflight(base_state(blocked=True)) == "end_blocked"


def test_after_preflight_over_budget_pauses():
    state = base_state(budget_status={"scope": "day"}, budget_approved=False)
    assert after_preflight(state) == "await_budget_confirmation"


def test_after_preflight_approved_budget_runs():
    state = base_state(budget_status={"scope": "day"}, budget_approved=True)
    assert after_preflight(state) == "execute_tool"


def test_after_await_budget_confirmation():
    assert after_await_budget_confirmation(base_state()) == "execute_tool"
    denied = base_state(final_response="Okay, I didn't run that.")
    assert after_await_budget_confirmation(denied) == "record_trace"


# ── after_execute_tool ────────────────────────────────────────────────────────


def test_after_execute_tool_without_a_park_goes_to_correlate():
    state = base_state(subtask_results=[])
    assert after_execute_tool(state) == "correlate"


def test_after_execute_tool_with_an_open_confirmation_pauses():
    state = base_state(write_confirmation=object(), parked_subtasks=[object()])
    assert after_execute_tool(state) == "await_write_confirmation"


def test_after_execute_tool_compound_also_goes_to_correlate():
    from ze_agents.types import AgentResult

    results = [AgentResult(agent="research", response="data")]
    state = base_state(
        subtask_results=results,
        envelope=make_envelope(is_compound=True, agents=("research", "companion")),
    )
    assert after_execute_tool(state) == "correlate"


# ── after_correlate ───────────────────────────────────────────────────────────


def test_after_correlate_single_goes_to_record_trace():
    state = base_state(subtask_results=[])
    assert after_correlate(state) == "record_trace"


def test_after_correlate_compound_goes_to_synthesize():
    from ze_agents.types import AgentResult

    results = [AgentResult(agent="research", response="data")]
    state = base_state(
        subtask_results=results,
        envelope=make_envelope(is_compound=True, agents=("research", "companion")),
    )
    assert after_correlate(state) == "synthesize"


def test_after_correlate_compound_no_results_goes_to_record_trace():
    state = base_state(
        subtask_results=[],
        envelope=make_envelope(is_compound=True, agents=("research", "companion")),
    )
    assert after_correlate(state) == "record_trace"
