from __future__ import annotations

from ze_seed.narrative.loader import load_persona


def test_seeded_traces_read_tool_duration_from_the_yaml():
    traces = [m.trace for m in load_persona().messages if m.trace is not None]
    assert traces
    assert [t.tool_duration_ms for t in traces][0] == 1200
    assert all(t.tool_duration_ms > 0 for t in traces)
