from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ze_agents.park import ParkedLoop


class ZeCoreError(Exception):
    """Base exception for all Ze errors."""


# Alias so ze-agents consumers can use the canonical name.
ZeError = ZeCoreError


# ── Routing ───────────────────────────────────────────────────────────────────


class RoutingError(ZeCoreError):
    """Routing failed after all attempts."""


class InvalidPromptError(RoutingError):
    """Prompt is empty or invalid."""


# ── Agents ────────────────────────────────────────────────────────────────────


class AgentError(ZeCoreError):
    """An agent failed during execution."""


class AgentTimeoutError(AgentError):
    """Agent exceeded its configured timeout."""


class UnknownAgentError(AgentError):
    """No agent registered for the requested name."""


class AgentConfigError(AgentError):
    """Agent or tool misconfiguration detected at startup."""


# ── Derivation and lifetimes ──────────────────────────────────────────────────


class UndeclaredDerivationError(AgentConfigError):
    """An AgentContext field has no row in the derivation table."""


class UndeclaredLifetimeError(AgentConfigError):
    """A graph-state field declares no lifetime (Turn, Input, Thread or Run)."""


# ── Interface ─────────────────────────────────────────────────────────────────


class InterfaceError(ZeCoreError):
    """Base class for interface errors."""


class InterfaceConfigError(InterfaceError):
    """AppInterface implementation is misconfigured."""


# ── Capability ────────────────────────────────────────────────────────────────


class CapabilityError(ZeCoreError):
    """Capability gate error."""


# ── Memory ────────────────────────────────────────────────────────────────────


class MemoryError(ZeCoreError):
    """Memory store operation failed."""


# ── Tools ─────────────────────────────────────────────────────────────────────


class UnknownToolError(AgentError):
    """No tool registered for the requested name."""


class LoopParked(ZeCoreError):
    """An agent loop stopped because asks-first tool calls await the user's decision.

    Raised only by `agentic_loop`. Caught by `run_delegate`, the graph's tool
    execution node and the goal executor; it never reaches the model.
    """

    def __init__(self, loop: ParkedLoop) -> None:
        super().__init__(f"{loop.agent} parked {len(loop.all_parked())} write(s)")
        self.loop = loop


# ── UI ────────────────────────────────────────────────────────────────────────


class InvalidComponentError(ZeCoreError):
    """A UI component descriptor or action was built with invalid fields."""


class UiActionRefusedError(AgentError):
    """A screen-pressed tool action was refused before the tool ran."""


# ── Workflow ──────────────────────────────────────────────────────────────────


class RetryError(ZeCoreError):
    """Base class for reply-retry failures (Phase 165)."""


class RetryFailedError(RetryError):
    """A retry run did not produce a usable reply; the original reply is untouched."""


class RetryRewindError(RetryError):
    """The thread's checkpointed history cannot be rewound to before the reply."""


class VoiceInputError(ZeCoreError):
    """Base class for voice-recording failures."""


class AudioTooLongError(VoiceInputError):
    """The recording is over the length limit."""


class AudioUnreadableError(VoiceInputError):
    """The recording's length or content cannot be read."""


class AudioToolMissingError(VoiceInputError):
    """ffmpeg or ffprobe is not installed on the server."""


class TranscriptionFailedError(VoiceInputError):
    """The speech model did not return a transcript."""


class WorkflowError(ZeCoreError):
    """Base class for workflow errors."""


class WorkflowPlanError(WorkflowError):
    """Planner failed to produce a valid workflow plan."""


class WorkflowExecutionError(WorkflowError):
    """Step execution failed unrecoverably."""


# ── Goals ─────────────────────────────────────────────────────────────────────


class GoalError(ZeCoreError):
    """Base class for goal errors."""


class GoalPlanError(GoalError):
    """Goal planner returned an invalid or unparseable plan."""


class GoalExecutionError(GoalError):
    """A milestone failed during goal execution."""


class GoalLearningError(GoalError):
    """Goal learning validation or persistence failed."""


class GoalLearningEvidenceError(GoalLearningError):
    """A learning is missing required evidence or cites an invalid source."""


class GoalLearningPromotionError(GoalLearningError):
    """FACT publication of a learning was blocked or failed."""


# ── Persona ───────────────────────────────────────────────────────────────────


class PersonaError(ZeCoreError):
    """Base class for persona errors."""


class UnknownProfileError(PersonaError):
    """Named persona profile not found."""


class UnknownDialError(PersonaError):
    """Named persona dial not found."""


# ── OpenRouter ────────────────────────────────────────────────────────────────


class OpenRouterError(ZeCoreError):
    """OpenRouter API call failed."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(OpenRouterError):
    """OpenRouter returned HTTP 429."""


class GenerationUnavailableError(OpenRouterError):
    """OpenRouter has no cost record for a generation id (HTTP 400 or 404), now or ever."""


# ── LLM output ────────────────────────────────────────────────────────────────


class LLMJsonParseError(ZeCoreError):
    """An LLM reply did not contain the JSON value the caller asked for."""

    def __init__(self, message: str, raw: str | None = None) -> None:
        super().__init__(message)
        self.raw = raw


# ── Harness ───────────────────────────────────────────────────────────────────


class AgentAbortedError(AgentError):
    """Raised inside agentic_loop when an AbortToken fires or on_loop_start aborts."""

    def __init__(self, reason: str | None = None) -> None:
        super().__init__(reason or "aborted")
        self.reason = reason


class HookAbort(AgentError):
    """Raised from HarnessHook.on_tool_start to skip a single tool call.

    The loop records the skipped call and continues to the next LLM turn.
    """

    def __init__(
        self, tool_name: str, reason: str = "", result: object | None = None
    ) -> None:
        super().__init__(f"hook aborted {tool_name!r}: {reason}")
        self.tool_name = tool_name
        self.reason = reason
        self.result = result


# ── Onboarding ────────────────────────────────────────────────────────────────


class OnboardingError(ZeCoreError):
    """Onboarding flow failed or received an invalid submission."""


# ── Channels ──────────────────────────────────────────────────────────────────


class ChannelError(ZeCoreError):
    """Base class for channel errors."""


class ChannelNotFoundError(ChannelError):
    """No channel registered for the requested channel type."""


class ChannelSendError(ChannelError):
    """Channel transport failed during send."""


# ── Claims ────────────────────────────────────────────────────────────────────


class ClaimError(ZeCoreError):
    """Base class for claim-topology errors."""


class MissingDecayParameterError(ClaimError):
    """Caller omitted a parameter its decay_profile requires."""


# ── Contribution seam ─────────────────────────────────────────────────────────


class ContributionError(ZeCoreError):
    """Base class for contribution-seam write-path errors."""


class UnlicensedClaimKindError(ContributionError):
    """A contribution's claim_kind is not licensed for its source_function."""


class MissingEvidenceError(ContributionError):
    """An INFERENCE/SUSPICION contribution has no evidence."""


class DanglingEvidenceError(ContributionError):
    """A cited evidence reference does not exist."""


class ActionRecordPayloadError(ContributionError):
    """ACTION_RECORD payload missing or paired with the wrong claim kind."""


class FeedbackRecordPayloadError(ContributionError):
    """FEEDBACK_RECORD payload missing or paired with the wrong claim kind."""


class FeedbackRecordValidationError(ContributionError):
    """Feedback record fields failed validation before persist."""


class FeedbackRecordIdempotencyConflictError(ContributionError):
    """Reuse of a feedback idempotency key with a materially different draft."""


class ActionRecordValidationError(ContributionError):
    """Action record fields failed validation before persist."""


class ActionRecordIdempotencyConflictError(ContributionError):
    """Reuse of an idempotency key with a materially different draft."""
