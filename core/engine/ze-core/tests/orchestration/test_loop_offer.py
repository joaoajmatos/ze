from types import SimpleNamespace

import pytest

from ze_core.orchestration.loop_offer import with_loop_offer_line
from ze_core.orchestration.nodes.trace import record_trace
from ze_core.routing.types import RoutingEnvelope, SubTask

IDS = ["11111111-1111-1111-1111-111111111111"]


class TestWithLoopOfferLine:
    def test_english_reply_gets_english_line(self):
        out = with_loop_offer_line(
            "Here is what is on your plate.", "what's on my plate?", IDS
        )
        assert out.startswith("Here is what is on your plate.\n\n")
        assert out.endswith("Want me to keep tracking it?")

    def test_portuguese_reply_gets_european_portuguese_line(self):
        out = with_loop_offer_line(
            "Tens duas coisas em aberto.", "o que tenho em aberto?", IDS
        )
        assert out.endswith("Queres que continue a acompanhá-la?")

    def test_plural_in_both_languages(self):
        ids = IDS + ["22222222-2222-2222-2222-222222222222"]
        en = with_loop_offer_line("Sure.", "hello there", ids)
        pt = with_loop_offer_line("Claro.", "olá, tudo bem?", ids)
        assert en.endswith("Want me to keep tracking them?")
        assert pt.endswith("Queres que continue a acompanhá-las?")

    def test_unknown_language_falls_back_to_english(self):
        out = with_loop_offer_line("ok", "ok", IDS)
        assert out.endswith("Want me to keep tracking it?")

    @pytest.mark.parametrize(
        "reply", ["Anything else?", "Queres que acompanhe?  ", "Sure — keep it?\n"]
    )
    def test_reply_already_asking_is_untouched(self, reply):
        assert with_loop_offer_line(reply, "x", IDS) == reply

    def test_no_offer_ids_is_untouched(self):
        assert with_loop_offer_line("Done.", "x", []) == "Done."

    def test_empty_reply_is_untouched(self):
        assert with_loop_offer_line("", "x", IDS) == ""


def _state(**extra):
    envelope = RoutingEnvelope(
        primary_agent="companion",
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=False,
        subtasks=[SubTask(agent="companion", intent="reason", prompt="p")],
        requires_synthesis=False,
    )
    return {
        "session_id": "s1",
        "prompt": "o que tenho em aberto?",
        "envelope": envelope,
        "agent_result": SimpleNamespace(
            response="Tens duas coisas.", tool_calls=[], sources=[]
        ),
        "loop_offer_ids": IDS,
        **extra,
    }


class TestRecordTraceAppendsOffer:
    async def test_appends_line_to_final_response_and_trace_keeps_ids(self):
        result = await record_trace(_state(), {"configurable": {}})
        assert result["final_response"].startswith("Tens duas coisas.")
        assert result["final_response"].endswith("acompanhá-la?")
        assert result["message_trace"].loop_offer_ids == IDS

    async def test_uses_final_response_when_set(self):
        result = await record_trace(
            _state(final_response="Tens X.\n\n---\nnota"), {"configurable": {}}
        )
        assert result["final_response"].startswith("Tens X.\n\n---\nnota\n\n")

    async def test_no_offer_leaves_response_alone(self):
        result = await record_trace(_state(loop_offer_ids=[]), {"configurable": {}})
        assert "final_response" not in result

    async def test_reply_already_asking_adds_nothing(self):
        state = _state()
        state["agent_result"].response = "Tens duas coisas. Queres acompanhá-las?"
        result = await record_trace(state, {"configurable": {}})
        assert "final_response" not in result
