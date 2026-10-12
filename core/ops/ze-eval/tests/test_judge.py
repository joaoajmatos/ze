import pytest

from ze_eval.judge import JudgeParseError, parse_judge_reply

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
    assert (score.quality, score.tone, score.tool_use, score.pass_) == (4, 5, None, True)


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
