from ze_priority.errors import (
    PriorityOverrideNotFoundError,
    StaleReprioritizationTargetError,
    ZePriorityError,
)
from ze_priority.types import (
    GoalSignal,
    HypothesisSignal,
    LoopSignal,
    MergedPriorityItem,
    OpenItemMention,
    PriorityCandidateRef,
    PriorityItem,
    PriorityOverride,
    PriorityOverrideRequest,
    PriorityRanking,
    SourceKind,
    SourceSignal,
)
from ze_priority.turn import TurnSurfacing
from ze_priority.view import PriorityView

_AGENT_MODULE_PATHS = ["ze_priority.tools", "ze_priority.agent"]


def agent_module_paths() -> list[str]:
    return list(_AGENT_MODULE_PATHS)


def import_agent_modules() -> None:
    import importlib

    for module_path in _AGENT_MODULE_PATHS:
        importlib.import_module(module_path)


__all__ = [
    "GoalSignal",
    "HypothesisSignal",
    "LoopSignal",
    "MergedPriorityItem",
    "OpenItemMention",
    "PriorityCandidateRef",
    "PriorityItem",
    "PriorityOverride",
    "PriorityOverrideNotFoundError",
    "PriorityOverrideRequest",
    "PriorityRanking",
    "PriorityView",
    "SourceKind",
    "SourceSignal",
    "StaleReprioritizationTargetError",
    "TurnSurfacing",
    "ZePriorityError",
    "agent_module_paths",
    "import_agent_modules",
]
