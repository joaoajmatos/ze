"""POST /eval/chat returns the rendered components so the judge can read them."""

from __future__ import annotations

from types import SimpleNamespace

from ze_agents.types import AgentResult
from ze_api.api.eval.router import _turn_response


def _outcome(components):
    return SimpleNamespace(
        error=None,
        interrupted=False,
        final_state={
            "agent_result": AgentResult(agent="research", response="Done."),
            "final_response": "Done.",
            "components": components,
        },
    )


def test_turn_response_carries_rendered_components():
    table = {"type": "table", "headers": ["A"], "rows": [["1"]]}
    response = _turn_response("s1", _outcome([table]))
    assert response.components == [table]


def test_turn_response_has_no_components_when_none_rendered():
    assert _turn_response("s1", _outcome(None)).components == []
