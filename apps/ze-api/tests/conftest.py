import importlib

import pytest

import ze_personal.contacts.tools  # noqa: F401 — registers get_contact_channels, set_contact_channel
import ze_browser.tool  # noqa: F401 — registers browser_extract
import ze_components.tools  # noqa: F401 — registers all render tools

# Ensure CalendarPlugin agent modules are imported so @agent decorators fire.
for _path in [
    "ze_calendar.agents.calendar.agent",
    "ze_calendar.agents.reminders.agent",
]:
    importlib.import_module(_path)


def _registry_has_real_agents() -> bool:
    from ze_agents.registry import get_registered_agents

    agents = get_registered_agents()
    if "research" not in agents:
        return False
    if "calendar" not in agents:
        return False
    return not any(cls.__name__.startswith("GateConfig_") for cls in agents.values())


@pytest.fixture(autouse=True)
def _ensure_real_agent_registry():
    """Keep ze-core registry on real @agent classes, not capability test stubs."""
    from ze_agents.bootstrap import reload_agent_modules

    from tests.support.agent_modules import ALL_AGENT_MODULE_PATHS

    if not _registry_has_real_agents():
        reload_agent_modules(ALL_AGENT_MODULE_PATHS)
    yield
    if not _registry_has_real_agents():
        reload_agent_modules(ALL_AGENT_MODULE_PATHS)


class FakeTranscribeClient:
    """Stands in for OpenRouterClient.transcribe; records each call."""

    def __init__(self, reply="remind me to call Ana", error=None):
        self.reply = reply
        self.error = error
        self.calls: list[dict] = []

    async def transcribe(self, audio_bytes, audio_format, model, duration_seconds=None):
        self.calls.append(
            {"audio_format": audio_format, "model": model, "duration_seconds": duration_seconds}
        )
        if self.error is not None:
            raise self.error
        return self.reply


class _StubProcess:
    def __init__(self, stdout: bytes, returncode: int):
        self._stdout = stdout
        self.returncode = returncode

    async def communicate(self, input=None):
        return self._stdout, b""

    def kill(self):
        pass

    async def wait(self):
        return self.returncode


class FfprobeStub:
    """Scripted subprocess results in call order: stdout text, or None for exit 1."""

    def __init__(self, outputs, missing=False):
        self.outputs = list(outputs)
        self.missing = missing
        self.calls: list[tuple] = []

    async def __call__(self, *argv, **kwargs):
        self.calls.append(argv)
        if self.missing:
            raise FileNotFoundError(argv[0])
        out = self.outputs.pop(0) if self.outputs else None
        return _StubProcess((out or "").encode(), 0 if out is not None else 1)


@pytest.fixture
def ffprobe_stub(monkeypatch):
    import asyncio

    def install(outputs=(), missing=False) -> FfprobeStub:
        stub = FfprobeStub(outputs, missing=missing)
        monkeypatch.setattr(asyncio, "create_subprocess_exec", stub)
        return stub

    return install
