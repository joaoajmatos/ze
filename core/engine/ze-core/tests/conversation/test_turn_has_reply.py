from ze_core.conversation.turn import TurnResult


def _result(response, components=None):
    return TurnResult(
        final_state={"components": components or []},
        config={},
        interrupted=False,
        response=response,
    )


def test_text_is_a_reply():
    assert _result("hi").has_reply


def test_components_without_text_are_a_reply():
    assert _result("", [{"type": "table"}]).has_reply


def test_neither_is_not_a_reply():
    assert not _result("").has_reply
    assert not _result(None).has_reply


def test_helper_accepts_any_outcome_shape():
    from types import SimpleNamespace

    from ze_core.conversation.turn import turn_has_reply

    assert turn_has_reply(SimpleNamespace(response="x"))
    assert turn_has_reply(
        SimpleNamespace(response=None, final_state={"components": [{"type": "t"}]})
    )
    assert not turn_has_reply(SimpleNamespace(response=None, final_state=None))
