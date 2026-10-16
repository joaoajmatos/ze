import pytest

from datetime import date

from ze_eval.judge import JudgeParseError, build_prompt, parse_judge_reply

_BODY = '{"quality": 4, "tone": 5, "tool_use": null, "pass": true, "reasoning": "ok"}'


@pytest.mark.parametrize(
    "content",
    [
        _BODY,
        f"```json\n{_BODY}\n```",
        f"```\n{_BODY}\n```",
        f"Here is my verdict:\n{_BODY}\nHope that helps.",
    ],
)
def test_parses_fenced_and_prose_wrapped_json(content):
    score = parse_judge_reply(content)
    assert (score.quality, score.tone, score.tool_use, score.pass_) == (
        4,
        5,
        None,
        True,
    )


@pytest.mark.parametrize("content", [None, "", "   "])
def test_empty_reply_has_clear_error(content):
    with pytest.raises(JudgeParseError, match="empty reply"):
        parse_judge_reply(content, model="m/x")


def test_non_json_reply_includes_snippet():
    with pytest.raises(JudgeParseError, match="starts with: 'I cannot"):
        parse_judge_reply("I cannot grade this.", model="m/x")


def test_missing_field_is_reported():
    with pytest.raises(JudgeParseError, match="KeyError"):
        parse_judge_reply('{"quality": 3}')


def _prompt(**kw):
    return build_prompt(
        description="d",
        prompt="p",
        response="r",
        expected_agent=None,
        agent_used="goals",
        criteria=["c"],
        today=date(2026, 10, 12),
        **kw,
    )


def test_prompt_shows_parked_tool_calls_and_pending_confirmation():
    text = _prompt(
        tool_calls=[{"tool_name": "delete_event", "gate": "parked", "parked": True}],
        pending_confirmation=True,
    )
    assert "- delete_event (parked)" in text
    assert "Waiting for the user's confirmation: yes" in text


def test_prompt_explains_that_a_parked_call_counts_as_invoking_the_tool():
    text = _prompt()
    assert (
        'a call marked "parked" waits for the user\'s approval; it counts as invoking the tool'
        in text
    )
    assert "draft" not in text


@pytest.mark.parametrize(
    ("call", "shown"),
    [
        ({"gate": "approved", "success": True}, "ok (approved)"),
        ({"gate": "pre_approved", "success": True}, "ok (pre_approved)"),
        ({"gate": "denied", "success": False}, "denied"),
        ({"gate": "expired", "success": False}, "expired"),
        ({"gate": "refused_over_cap", "success": False}, "refused_over_cap"),
        ({"gate": "none", "success": True}, "ok"),
        ({"gate": "none", "success": False}, "failed"),
        ({"success": True}, "ok"),
    ],
)
def test_prompt_shows_the_gate_state_of_each_call(call, shown):
    text = _prompt(tool_calls=[{"tool_name": "t", **call}])
    assert f"- t ({shown})" in text


def test_prompt_states_the_date_and_empty_tool_list():
    text = _prompt()
    assert "Today's date: 2026-10-12" in text
    assert "- none recorded" in text
    assert "Waiting for the user's confirmation: no" in text


def test_prompt_labels_the_turn_a_tool_call_came_from():
    text = _prompt(tool_calls=[{"tool_name": "search", "turn": 1}])
    assert "- [turn 1] search (ok)" in text


def test_a_duplicate_call_is_shown_as_not_run():
    from ze_eval.judge import format_tool_calls

    text = format_tool_calls(
        [{"tool_name": "cancel_reminder", "success": True, "gate": "duplicate"}]
    )
    assert text == "- cancel_reminder (duplicate)"
