"""Real ffprobe against the recorded fixtures (skipped without the binary)."""

import shutil
from pathlib import Path

import pytest

from ze_agents.errors import AudioUnreadableError
from ze_core.openrouter.audio import probe_duration

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe not installed"),
]

FIXTURES = Path(__file__).resolve().parents[5] / "apps/ze-api/tests/fixtures/audio"


@pytest.mark.parametrize(
    ("name", "mime"),
    [
        ("stream.webm", "audio/webm;codecs=opus"),
        ("stream.ogg", "audio/ogg"),
        ("frag.mp4", "audio/mp4"),
    ],
)
async def test_probe_reads_three_second_fixture(name, mime):
    duration = await probe_duration((FIXTURES / name).read_bytes(), mime)
    assert duration == pytest.approx(3.0, abs=0.1)


async def test_wav_labelled_as_webm_is_rejected():
    with pytest.raises(AudioUnreadableError):
        await probe_duration((FIXTURES / "one_second.wav").read_bytes(), "audio/webm")
