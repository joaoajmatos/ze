"""The Haiku fallback's speech-act labels match `SpeechAct`, and only `fact` admits a fact (173)."""

from __future__ import annotations

import re

import pytest

from ze_memory.extractor import _SYSTEM, admit_speech_act, parse_fact_response
from ze_memory.types import SpeechAct


def _prompt_labels() -> set[str]:
    match = re.search(r"speech_act must be one of:\s*(.+?)\.\s*\n", _SYSTEM, re.DOTALL)
    assert match is not None
    return {label.strip() for label in match.group(1).split(",")}


def test_prompt_label_list_equals_the_enum():
    assert _prompt_labels() == {act.value for act in SpeechAct}


def test_prompt_reply_shape_lists_the_same_labels():
    shape = re.search(r'"speech_act": "<([^>]+)>"', _SYSTEM)
    assert shape is not None
    assert set(shape.group(1).split("|")) == {act.value for act in SpeechAct}


@pytest.mark.parametrize(
    "label", ["reminder", "loop", "goal", "drop", "unknown", "", None]
)
def test_commitment_only_or_unknown_labels_map_to_none(label):
    assert admit_speech_act(label) is SpeechAct.NONE


@pytest.mark.parametrize("act", list(SpeechAct), ids=lambda a: a.value)
def test_only_fact_admits_a_fact(act):
    raw = (
        '{"speech_act": "%s", "family": "preference", '
        '"facts": [{"value": "prefers aisle seats", "confidence": 0.9}]}' % act.value
    )
    admitted = parse_fact_response(raw)
    assert bool(admitted) is (act is SpeechAct.FACT)


@pytest.mark.parametrize("label", ["reminder", "loop", "goal", "drop"])
def test_a_commitment_label_in_the_reply_admits_no_fact(label):
    raw = (
        '{"speech_act": "%s", "family": "preference", '
        '"facts": [{"value": "prefers aisle seats", "confidence": 0.9}]}' % label
    )
    assert parse_fact_response(raw) == []
