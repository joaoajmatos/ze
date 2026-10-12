import pytest

from ze_agents.errors import LLMJsonParseError, ZeError
from ze_agents.llm_json import parse_llm_json


@pytest.mark.parametrize(
    "raw",
    [
        '{"a": 1}',
        '  {"a": 1}\n',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        '```JSON\n{"a": 1}```',
        '```json\n{"a": 1}\n',
        'Sure! Here is the result:\n```json\n{"a": 1}\n```\nHope that helps.',
        'Here you go: {"a": 1} — let me know.',
        'Note {not json} first. {"a": 1}',
    ],
)
def test_object_shapes(raw):
    assert parse_llm_json(raw, expect=dict) == {"a": 1}


@pytest.mark.parametrize(
    "raw",
    ["[1, 2]", "```json\n[1, 2]\n```", "The list is [1, 2] as requested."],
)
def test_array_shapes(raw):
    assert parse_llm_json(raw, expect=list) == [1, 2]


def test_expect_rejects_other_type():
    with pytest.raises(LLMJsonParseError):
        parse_llm_json("[1, 2]", expect=dict)


def test_unwrapped_scalar_without_expect():
    assert parse_llm_json("0.5") == 0.5


@pytest.mark.parametrize("raw", ["", "   ", None, 3, "no json here", '{"a": '])
def test_failure_is_typed(raw):
    with pytest.raises(LLMJsonParseError) as exc:
        parse_llm_json(raw)
    assert isinstance(exc.value, ZeError)
