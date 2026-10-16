"""Park types for write confirmation (Phase 181).

An asks-first tool call is parked, not run. The loop that parked it is saved as a
`ParkedLoop` so the run can resume with the user's decision. Every type here is a
JSON-safe dataclass in the checkpoint serde allow-list. Only the model's own
arguments are saved: injected dependencies are re-merged when an approved call runs.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ze_agents.types import ToolCall

DECLINED_RESULT = (
    "The user declined; nothing was done. This was their choice, not an error: "
    "do not retry it or suggest a fix."
)
OVER_CAP_RESULT = "This needs the user's approval; ask them in your reply instead."
DUPLICATE_RESULT = (
    "The user approved this exact call once; it runs in another step of this turn "
    "and was not repeated here."
)

MAX_WRITE_ROUNDS = 3
SUMMARY_MAX_CHARS = 160

# Set by `call_tool` while an approved or pre-approved tool body runs, so a producer
# that records an action (`ActionRecorder`) can cite the approval (FR-030).
current_approval: ContextVar[dict[str, Any] | None] = ContextVar(
    "current_approval", default=None
)


@dataclass(frozen=True)
class ApprovedCall:
    """The user approved this parked call. Built only by the resume path, from park state.

    Runtime only, never checkpointed. Approval is this object, never a value a model
    can put in its tool arguments.
    """

    call_id: str


ParkReason = Literal["asks_first", "constraint", "check"]
DecisionOutcome = Literal[
    "approved", "edited", "denied", "timed_out", "superseded", "duplicate"
]
ConfirmationKind = Literal["write", "budget", "held"]
ConfirmationStatus = Literal["open", "approved", "denied", "timed_out", "superseded"]


@dataclass
class ParkedWrite:
    item_id: str
    call_id: str
    tool: str
    args: dict[str, Any]
    effect_phrase: str
    summary: str
    agent: str
    editable_field: str | None = None
    conflict: str | None = None
    reason: ParkReason = "asks_first"


@dataclass
class ParkedLoop:
    agent: str
    messages: list[dict[str, Any]]
    accumulated: list[ToolCall]
    iteration: int
    parked: list[ParkedWrite] = field(default_factory=list)
    child: ParkedLoop | None = None
    child_call_id: str | None = None
    child_arguments: dict[str, Any] | None = None

    def all_parked(self) -> list[ParkedWrite]:
        """This loop's parked writes followed by every nested child's, in order."""
        items = list(self.parked)
        if self.child is not None:
            items.extend(self.child.all_parked())
        return items


@dataclass
class ParkedSubtask:
    index: int
    loop: ParkedLoop


@dataclass
class WriteDecision:
    item_id: str
    outcome: DecisionOutcome
    edited_text: str | None = None


@dataclass
class ConfirmItem:
    item_id: str
    agent: str
    tool: str | None
    effect_phrase: str
    summary: str
    editable_field: str | None = None
    proposed_text: str | None = None
    conflict: str | None = None


@dataclass
class WriteConfirmation:
    request_id: str
    kind: ConfirmationKind
    round: int
    items: list[ConfirmItem] = field(default_factory=list)
    status: ConfirmationStatus = "open"
    # item_id of a parked call identical (tool, args) to a shown item -> that item's id
    aliases: dict[str, str] = field(default_factory=dict)


def generic_summary(args: dict[str, Any]) -> str:
    """`key: value` pairs of the model's arguments, truncated to SUMMARY_MAX_CHARS."""
    text = ", ".join(f"{k}: {v}" for k, v in args.items() if v not in (None, ""))
    if len(text) > SUMMARY_MAX_CHARS:
        text = text[: SUMMARY_MAX_CHARS - 1].rstrip() + "…"
    return text
