from ze_agents.screen import ScreenContext


def test_voice_only_context_is_known_and_empty():
    ctx, warnings = ScreenContext.from_wire({"voice": {"transcription_id": "abc"}})
    assert warnings == []
    assert ctx.is_empty
    assert "voice" not in ctx.to_wire()
