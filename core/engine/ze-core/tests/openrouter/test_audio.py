"""Tests for ze_core.openrouter.audio (subprocess stubbed)."""

import pytest

from ze_agents.errors import AudioToolMissingError, AudioUnreadableError
from ze_core.openrouter.audio import (
    container_format,
    normalise_audio_format,
    probe_duration,
    to_mp3,
)


@pytest.mark.parametrize(
    ("mime", "expected"),
    [
        ("audio/webm;codecs=opus", "webm"),
        ("audio/mp4", "m4a"),
        ("audio/x-wav", "wav"),
        ("audio/ogg; codecs=opus", "ogg"),
        ("audio/mpeg", "mp3"),
    ],
)
def test_normalise_audio_format(mime, expected):
    assert normalise_audio_format(mime) == expected


@pytest.mark.parametrize(
    ("mime", "expected"),
    [
        ("audio/mp4", "mp4"),
        ("audio/x-m4a", "mp4"),
        ("audio/webm;codecs=opus", "webm"),
        ("audio/ogg", "ogg"),
        ("audio/wav", "wav"),
    ],
)
def test_container_format(mime, expected):
    assert container_format(mime) == expected


async def test_probe_returns_step_one_duration(ffprobe_stub):
    stub = ffprobe_stub(["3.400000\n"])
    assert await probe_duration(b"x", "audio/wav") == pytest.approx(3.4)
    assert len(stub.calls) == 1


@pytest.mark.parametrize("first", ["0\n", "-1.5\n", "N/A\n", None])
async def test_probe_falls_back_to_packet_scan(ffprobe_stub, first):
    stub = ffprobe_stub([first, "0.000000,0.020000\n2.994000,0.020000\n"])
    assert await probe_duration(b"x", "audio/webm") == pytest.approx(3.014)
    assert len(stub.calls) == 2


async def test_probe_unreadable_when_both_steps_fail(ffprobe_stub):
    ffprobe_stub(["N/A\n", None])
    with pytest.raises(AudioUnreadableError):
        await probe_duration(b"x", "audio/webm")


async def test_probe_unreadable_when_scan_has_no_packets(ffprobe_stub):
    ffprobe_stub(["N/A\n", ""])
    with pytest.raises(AudioUnreadableError):
        await probe_duration(b"x", "audio/webm")


async def test_probe_tool_missing(ffprobe_stub):
    ffprobe_stub([], missing=True)
    with pytest.raises(AudioToolMissingError):
        await probe_duration(b"x", "audio/wav")


async def test_probe_hang_kills_process(ffprobe_stub):
    stub = ffprobe_stub(["3\n"], hang=True)
    with pytest.raises(AudioUnreadableError):
        await probe_duration(b"x", "audio/wav", timeout=0.05)
    assert stub.processes[0].killed


async def test_probe_forces_demuxer_and_whitelist(ffprobe_stub):
    stub = ffprobe_stub(["N/A\n", "1.0,0.5\n"])
    await probe_duration(b"x", "audio/mp4")
    for argv in stub.calls:
        assert argv[argv.index("-f") + 1] == "mp4"
        assert argv[argv.index("-protocol_whitelist") + 1] == "pipe"


async def test_to_mp3_returns_output(ffprobe_stub):
    ffprobe_stub(["mp3-bytes"])
    assert await to_mp3(b"x", "webm") == b"mp3-bytes"


async def test_to_mp3_nonzero_exit(ffprobe_stub):
    ffprobe_stub([None])
    with pytest.raises(AudioUnreadableError):
        await to_mp3(b"x", "webm")


async def test_to_mp3_timeout(ffprobe_stub):
    stub = ffprobe_stub(["x"], hang=True)
    with pytest.raises(AudioUnreadableError):
        await to_mp3(b"x", "webm", timeout=0.05)
    assert stub.processes[0].killed


async def test_to_mp3_tool_missing(ffprobe_stub):
    ffprobe_stub([], missing=True)
    with pytest.raises(AudioToolMissingError):
        await to_mp3(b"x", "webm")
