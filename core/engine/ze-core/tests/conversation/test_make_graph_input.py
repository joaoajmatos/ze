from ze_agents.interface.types import RawInput, VoiceInput
from ze_core.conversation.turn import make_graph_input


def test_voice_turn_sets_modality_and_voice_input():
    graph_input = make_graph_input(
        RawInput(text="hello", voice=VoiceInput(duration_s=3.5, edited=True)), "s"
    )
    assert graph_input["input_modality"] == "voice"
    assert graph_input["voice_input"] == {"duration_s": 3.5, "edited": True}
    assert graph_input["prompt"] == "hello"


def test_text_turn_has_no_voice_input_and_key_resets():
    graph_input = make_graph_input(RawInput(text="hello"), "s")
    assert graph_input["input_modality"] == "text"
    assert "voice_input" in graph_input
    assert graph_input["voice_input"] is None
