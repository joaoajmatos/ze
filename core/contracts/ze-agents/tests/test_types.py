from dataclasses import dataclass

from ze_agents.claims import ClaimKind, Provenance
from ze_agents.types import AgentResult, ClaimBearingProposal


@dataclass
class _FakeProposal:
    claim_kind: ClaimKind
    provenance: Provenance
    confidence: float


def test_shape_matching_object_satisfies_protocol():
    proposal = _FakeProposal(
        claim_kind=ClaimKind.IDENTITY,
        provenance=Provenance.SYNTHESIZED,
        confidence=0.9,
    )
    assert isinstance(proposal, ClaimBearingProposal)


def test_object_missing_fields_does_not_satisfy_protocol():
    class _Bare:
        pass

    assert not isinstance(_Bare(), ClaimBearingProposal)


def test_agent_result_proposal_fields_default_to_empty_list():
    result = AgentResult(agent="companion", response="hi")
    assert result.contact_proposals == []


def test_tool_calls_get_distinct_call_ids_and_no_start():
    from ze_agents.types import ToolCall

    a = ToolCall(tool_name="t", args={}, result=None, duration_ms=1, success=True)
    b = ToolCall(tool_name="t", args={}, result=None, duration_ms=1, success=True)
    assert a.call_id and b.call_id and a.call_id != b.call_id
    assert a.started_at is None


def test_parked_write_gets_a_fresh_trace_call_id_per_park():
    from ze_agents.park import ParkedWrite

    def park() -> ParkedWrite:
        return ParkedWrite(
            item_id="i",
            call_id="call_0",
            tool="send",
            args={},
            effect_phrase="sent",
            summary="s",
            agent="messenger",
        )

    assert park().trace_call_id != park().trace_call_id


def test_tool_sink_defaults_to_none_and_stays_out_of_repr():
    from ze_agents.types import AgentContext

    ctx = AgentContext(session_id="s", prompt="p", tool_sink=lambda call: None)
    assert AgentContext(session_id="s", prompt="p").tool_sink is None
    assert "tool_sink" not in repr(ctx)


def test_script_fields_default_empty_and_runner_stays_out_of_repr():
    from ze_agents.types import AgentContext, ToolCall

    call = ToolCall(tool_name="t", args={}, result="", duration_ms=1, success=True)
    assert call.parent_call_id is None
    assert call.inner_calls == []
    assert call.script is None
    assert call.inner_calls is not ToolCall(
        tool_name="t", args={}, result="", duration_ms=1, success=True
    ).inner_calls

    runner = object()
    ctx = AgentContext(session_id="s", prompt="p", script_runner=runner)
    assert AgentContext(session_id="s", prompt="p").script_runner is None
    assert "script_runner" not in repr(ctx)
