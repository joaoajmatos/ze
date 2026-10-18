import pytest
from ze_agents.errors import (
    AudioTooLongError,
    AudioToolMissingError,
    AudioUnreadableError,
    TranscriptionFailedError,
    VoiceInputError,
    ZeError,
)


def test_voice_input_error_is_a_ze_error():
    assert issubclass(VoiceInputError, ZeError)


@pytest.mark.parametrize(
    "cls",
    [
        AudioTooLongError,
        AudioUnreadableError,
        AudioToolMissingError,
        TranscriptionFailedError,
    ],
)
def test_voice_errors_subclass_voice_input_error(cls):
    assert issubclass(cls, VoiceInputError)
