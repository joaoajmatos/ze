import json

import pytest

from ze_memory.extractor import admit_speech_act, parse_fact_response
from ze_memory.types import SpeechAct


@pytest.mark.parametrize(
    ("payload", "expected_act", "expect_facts"),
    [
        (
            {
                "speech_act": "none",
                "family": "drop",
                "facts": [{"value": "call dentist Tuesday 3"}],
            },
            SpeechAct.NONE,
            [],
        ),
        (
            {
                "speech_act": "none",
                "family": "drop",
                "facts": [{"value": "I'll call Mom Tuesday"}],
            },
            SpeechAct.NONE,
            [],
        ),
        (
            {
                "speech_act": "none",
                "family": "drop",
                "facts": [{"value": "remember to call Mom Tuesday at 3"}],
            },
            SpeechAct.NONE,
            [],
        ),
        (
            {
                "speech_act": "none",
                "family": "drop",
                "facts": [{"value": "figure out whether to switch jobs"}],
            },
            SpeechAct.NONE,
            [],
        ),
        (
            {
                "speech_act": "none",
                "family": "drop",
                "facts": [{"value": "ship the thesis by June"}],
            },
            SpeechAct.NONE,
            [],
        ),
        (
            {
                "speech_act": "fact",
                "family": "constraint",
                "facts": [{"value": "never email after 22:00", "confidence": 0.9}],
            },
            SpeechAct.FACT,
            [
                {
                    "predicate": "constraint",
                    "value": "never email after 22:00",
                    "confidence": 0.9,
                }
            ],
        ),
        (
            {
                "speech_act": "none",
                "family": "drop",
                "facts": [{"value": "tired today"}],
            },
            SpeechAct.NONE,
            [],
        ),
        (
            {
                "speech_act": "clarify",
                "family": "drop",
                "facts": [{"value": "keep this in mind"}],
            },
            SpeechAct.CLARIFY,
            [],
        ),
        (
            {
                "speech_act": "ingest",
                "family": "drop",
                "facts": [{"value": "this PDF"}],
            },
            SpeechAct.INGEST,
            [],
        ),
        (
            {
                "speech_act": "none",
                "family": "drop",
                "facts": [{"value": "forget the dentist"}],
            },
            SpeechAct.NONE,
            [],
        ),
        (
            {
                "speech_act": "forget",
                "family": "drop",
                "facts": [{"value": "forget that I like aisle seats"}],
            },
            SpeechAct.FORGET,
            [],
        ),
    ],
)
def test_speech_act_gate_table(payload, expected_act, expect_facts):
    assert admit_speech_act(payload["speech_act"]) is expected_act
    assert parse_fact_response(json.dumps(payload)) == expect_facts


@pytest.mark.parametrize("raw", ["reminder", "loop", "goal", "drop", "banana", "", None])
def test_removed_and_unknown_labels_admit_as_none(raw):
    assert admit_speech_act(raw) is SpeechAct.NONE
