import asyncio
import logging

import pytest
import structlog


@pytest.fixture(autouse=True)
def _configure_test_logging():
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        processors=[
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )


class FakeTranscribeClient:
    """Stands in for OpenRouterClient.transcribe; records each call."""

    def __init__(self, reply: str = "hello there", error: Exception | None = None):
        self.reply = reply
        self.error = error
        self.calls: list[dict] = []

    async def transcribe(self, audio_bytes, audio_format, model, duration_seconds=None):
        self.calls.append(
            {
                "audio_bytes": audio_bytes,
                "audio_format": audio_format,
                "model": model,
                "duration_seconds": duration_seconds,
            }
        )
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture
def fake_transcribe_client():
    return FakeTranscribeClient()


class _StubProcess:
    def __init__(self, stdout: bytes, returncode: int, hang: bool):
        self._stdout = stdout
        self.returncode = returncode
        self._hang = hang
        self.killed = False

    async def communicate(self, input=None):
        if self._hang and not self.killed:
            await asyncio.sleep(3600)
        return self._stdout, b""

    def kill(self):
        self.killed = True
        self.returncode = -9

    async def wait(self):
        return self.returncode


class FfprobeStub:
    """Scripted subprocess results, one entry per call in order.

    An entry is stdout text (exit 0) or ``None`` (exit 1, no output). ``calls``
    records each argv.
    """

    def __init__(self, outputs, missing=False, hang=False):
        self.outputs = list(outputs)
        self.missing = missing
        self.hang = hang
        self.calls: list[tuple] = []
        self.processes: list[_StubProcess] = []

    async def __call__(self, *argv, **kwargs):
        self.calls.append(argv)
        if self.missing:
            raise FileNotFoundError(argv[0])
        out = self.outputs.pop(0) if self.outputs else None
        proc = _StubProcess(
            (out or "").encode(), 0 if out is not None else 1, self.hang
        )
        self.processes.append(proc)
        return proc


@pytest.fixture
def ffprobe_stub(monkeypatch):
    def install(outputs=(), missing=False, hang=False) -> FfprobeStub:
        stub = FfprobeStub(outputs, missing=missing, hang=hang)
        monkeypatch.setattr(asyncio, "create_subprocess_exec", stub)
        return stub

    return install
