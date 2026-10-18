from ze_agents.interface.types import RawInput, VoiceInput


def test_voice_input_fields():
    v = VoiceInput(duration_s=3.4, edited=True)
    assert v.duration_s == 3.4
    assert v.edited is True


def test_raw_input_voice_defaults_to_none():
    assert RawInput(text="hi").voice is None


def test_raw_input_carries_voice():
    raw = RawInput(text="hi", voice=VoiceInput(1.0, False))
    assert raw.voice == VoiceInput(1.0, False)
