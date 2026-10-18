"""A message that cites a live transcription becomes a voice turn (phase 192 US1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from ze_agents.interface.types import VoiceInput
from ze_api.api.ws.turns import handle_message
from ze_api.voice.registry import TranscriptionRegistry
from ze_core.conversation.messages.types import Message


def _env():
    container = MagicMock()
    container.translations = None
    container.transcription_registry = TranscriptionRegistry()
    container.invoke_raw_turn = AsyncMock(side_effect=RuntimeError("stop after config"))
    msgs = AsyncMock()
    conn = MagicMock()
    conn.take_pending_gate_redirect = MagicMock(return_value=None)
    conn.send_frame = AsyncMock()
    return container, msgs, conn


async def _send(container, msgs, conn, text: str, context):
    data = {"text": text, "thread_id": "t1"}
    if context is not None:
        data["context"] = context
    await handle_message(MagicMock(), data, container, msgs, conn, None)
    saved: Message = msgs.save.await_args.args[0]
    call = container.invoke_raw_turn.await_args
    return saved, call.args[1], call.kwargs["config_extra"]


def _voice_ctx(tid: str) -> dict:
    return {"voice": {"transcription_id": tid}}


async def test_live_reference_builds_a_voice_input_unedited():
    container, msgs, conn = _env()
    tid = container.transcription_registry.register("remind me to call Ana", 3.4)
    _, raw, _ = await _send(
        container, msgs, conn, "  remind me to call Ana \n", _voice_ctx(tid)
    )
    assert raw.text == "  remind me to call Ana \n"
    assert raw.voice == VoiceInput(duration_s=3.4, edited=False)


async def test_changed_text_is_marked_edited():
    container, msgs, conn = _env()
    tid = container.transcription_registry.register("remind me to call Ana", 3.4)
    _, raw, _ = await _send(
        container, msgs, conn, "remind me to call Anna", _voice_ctx(tid)
    )
    assert raw.voice == VoiceInput(duration_s=3.4, edited=True)


async def test_unknown_id_is_a_text_turn_with_a_log_and_no_warning(monkeypatch):
    from ze_api.api.ws import turns

    events: list[str] = []
    monkeypatch.setattr(turns.log, "info", lambda event, **kw: events.append(event))
    container, msgs, conn = _env()
    _, raw, extra = await _send(container, msgs, conn, "hello", _voice_ctx("nope"))
    assert raw.voice is None
    assert "ws_voice_ref_unknown" in events
    assert "screen_context_invalid" not in extra


async def test_expired_id_is_a_text_turn():
    container, msgs, conn = _env()
    clock = [0.0]
    container.transcription_registry = TranscriptionRegistry(clock=lambda: clock[0])
    tid = container.transcription_registry.register("hi", 1.0)
    clock[0] = 601
    _, raw, _ = await _send(container, msgs, conn, "hi", _voice_ctx(tid))
    assert raw.voice is None


async def test_voice_only_context_is_not_stored_as_screen_context():
    container, msgs, conn = _env()
    tid = container.transcription_registry.register("hi", 1.0)
    saved, _, extra = await _send(container, msgs, conn, "hi", _voice_ctx(tid))
    assert saved.screen_context is None
    assert "screen_context" not in extra


async def test_reference_is_reusable():
    container, msgs, conn = _env()
    tid = container.transcription_registry.register("hi", 1.0)
    _, first, _ = await _send(container, msgs, conn, "hi", _voice_ctx(tid))
    _, second, _ = await _send(container, msgs, conn, "hi", _voice_ctx(tid))
    assert first.voice is not None and second.voice is not None


async def test_text_turn_has_no_voice():
    container, msgs, conn = _env()
    _, raw, _ = await _send(container, msgs, conn, "hi", None)
    assert raw.voice is None


async def test_malformed_voice_ref_is_ignored():
    container, msgs, conn = _env()
    for bad in (
        {"voice": "x"},
        {"voice": {"transcription_id": 5}},
        {"voice": {"transcription_id": "a" * 65}},
    ):
        _, raw, _ = await _send(container, msgs, conn, "hi", bad)
        assert raw.voice is None
