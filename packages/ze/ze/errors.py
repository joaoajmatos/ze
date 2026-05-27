"""Ze application exceptions."""

from ze_core.errors import ZeCoreError as ZeError

# ── Capability ────────────────────────────────────────────────────────────────

class CapabilityError(ZeError):
    """Capability gate error."""


class CapabilityConfigError(CapabilityError):
    """capabilities.yaml could not be loaded or is invalid."""


# ── Memory ────────────────────────────────────────────────────────────────────

class MemoryError(ZeError):
    """Memory store operation failed."""


# ── OpenRouter ────────────────────────────────────────────────────────────────

class OpenRouterError(ZeError):
    """OpenRouter API call failed."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(OpenRouterError):
    """OpenRouter returned HTTP 429."""


# ── Workflow ───────────────────────────────────────────────────────────────────

class WorkflowError(ZeError):
    """Base class for workflow errors."""


class WorkflowPlanError(WorkflowError):
    """Planner failed to produce a valid workflow plan."""


class WorkflowExecutionError(WorkflowError):
    """Step execution failed unrecoverably."""


# ── Multimodal ─────────────────────────────────────────────────────────────────

class TranscriptionError(ZeError):
    """Audio file could not be transcribed by the Whisper model."""


class ImageDownloadError(ZeError):
    """Failed to download image bytes from Telegram's file server."""


# ── Channels ───────────────────────────────────────────────────────────────────

class ChannelError(ZeError):
    """Base class for communication channel errors."""


class ChannelNotFoundError(ChannelError):
    """No channel registered for the requested ChannelType."""


class ChannelSendError(ChannelError):
    """Channel transport failed during send."""
