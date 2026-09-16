from __future__ import annotations

from typing import Any, Literal

LEDGER_TERMINAL_STATUSES = frozenset({"done", "skipped", "denied"})
PROMOTE_OFFERED_STATUS = "promote_offered"

CONFIRMATION_TIMEOUT_BASE = (
    "I waited for your approval but the window elapsed — "
    "let me know if you'd like me to try again."
)
PROMOTE_OFFER_SUFFIX = (
    " If you want this job to keep going after this turn, tell me and I can "
    "continue it as a goal or as a workflow — not both, and not until you accept."
)

PromoteKind = Literal["goal", "workflow", "ask"]

_GOAL_HINTS = (
    "multi-week",
    "milestone",
    "thesis",
    "deadline",
    "keep going on this as a goal",
)
_WORKFLOW_HINTS = (
    "every week",
    "schedule",
    "recurring",
    "unattended",
    "keep going on this as a workflow",
)


def ledger_is_unfinished(ledger: list[dict[str, Any]] | None) -> bool:
    if not ledger:
        return False
    return any(
        (item.get("status") or "") not in LEDGER_TERMINAL_STATUSES for item in ledger
    )


def should_offer_promote(
    ledger: list[dict[str, Any]] | None,
    *,
    timeout_or_abort: bool = False,
) -> bool:
    """Offer a durable goal/workflow instance for an unfinished conductor job.

    Same-reply close does not stack on a 156 ask_user. Timeout/abort/user-left
    still offers even if the last status was ask_user or awaiting_confirmation.
    """
    if not ledger_is_unfinished(ledger):
        return False
    if timeout_or_abort:
        return True
    return not any(item.get("status") == "ask_user" for item in ledger)


def confirmation_timeout_message(ledger: list[dict[str, Any]] | None) -> str:
    if should_offer_promote(ledger, timeout_or_abort=True):
        return CONFIRMATION_TIMEOUT_BASE + PROMOTE_OFFER_SUFFIX
    return CONFIRMATION_TIMEOUT_BASE


def classify_promote_kind(text: str) -> PromoteKind:
    lowered = (text or "").casefold()
    if "goal" in lowered and "workflow" in lowered:
        return "ask"
    wants_goal = any(hint in lowered for hint in _GOAL_HINTS)
    wants_workflow = any(hint in lowered for hint in _WORKFLOW_HINTS)
    if wants_goal:
        return "goal"
    if wants_workflow:
        return "workflow"
    return "ask"


def ledger_with_promote_offer(
    ledger: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    items = [dict(item) for item in (ledger or [])]
    if should_offer_promote(items, timeout_or_abort=False):
        items.append({"agent": "companion", "status": PROMOTE_OFFERED_STATUS})
    return items
