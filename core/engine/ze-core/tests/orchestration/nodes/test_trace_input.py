"""MessageTrace.input — voice turns only, never the transcript."""

import json
from dataclasses import asdict
from types import SimpleNamespace

from ze_core.orchestration.nodes.trace import record_trace


def _envelope():
    return SimpleNamespace(
        primary_agent="companion",
        routing_method="embedding",
        confidence=0.8,
        score_gap=0.2,
        is_compound=False,
        subtasks=[],
    )


async def test_voice_turn_records_input_without_transcript():
    result = await record_trace(
        {
            "envelope": _envelope(),
            "agent_result": None,
            "prompt": "secret transcript words",
            "voice_input": {"duration_s": 4.2, "edited": False},
        },
        {"configurable": {}},
    )
    trace = result["message_trace"]
    assert trace.input.modality == "voice"
    assert trace.input.duration_s == 4.2
    assert trace.input.edited is False
    assert "secret transcript words" not in json.dumps(asdict(trace), default=str)


async def test_text_turn_has_no_input():
    result = await record_trace(
        {"envelope": _envelope(), "agent_result": None, "voice_input": None},
        {"configurable": {}},
    )
    assert result["message_trace"].input is None
