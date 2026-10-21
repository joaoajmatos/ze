from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from ze_agents.errors import AgentConfigError
from ze_logging import get_logger

log = get_logger(__name__)

__all__ = [
    "PRESET_LABEL_MAX",
    "PRESET_PROMPT_MAX",
    "SLOTS",
    "ModuleProvider",
    "ModuleResult",
    "ModuleSubject",
    "Slot",
    "UiContribution",
    "UiManifest",
    "collect_ui_contributions",
    "filter_ui_manifest_by_openapi",
    "get_module",
    "request_module_refresh",
]

Slot = Literal["mind.entity", "doing.run", "governance.connections"]
SLOTS: frozenset[str] = frozenset({"mind.entity", "doing.run", "governance.connections"})
PRESET_LABEL_MAX = 40
PRESET_PROMPT_MAX = 300
_KINDS = frozenset({"module", "preset", "settings_section"})


@dataclass(frozen=True)
class ModuleSubject:
    """What a module is asked about. Ze builds it from its own records, never from client text."""

    kind: Literal["entity", "workflow_run", "none"]
    id: str | None = None
    label: str | None = None
    entity_type: str | None = None
    parent_id: str | None = None


@dataclass(frozen=True)
class ModuleResult:
    """A provider's answer: whether the module applies, and serialized primitives if it does."""

    applies: bool
    components: list[dict[str, Any]] = field(default_factory=list)


ModuleProvider = Callable[[ModuleSubject], Awaitable[ModuleResult]]


@dataclass(frozen=True)
class UiContribution:
    """Declarative shell contribution from a plugin: a module, a preset or a settings section."""

    id: str
    plugin: str
    kind: str
    label: str
    icon: str
    slot: str | None = None
    provider: ModuleProvider | None = field(default=None, compare=False, repr=False)
    prompt: str | None = None
    settings_operation_id: str | None = None
    priority: int = 100


@dataclass(frozen=True)
class UiManifest:
    modules: tuple[UiContribution, ...]
    presets: tuple[UiContribution, ...]
    settings_sections: tuple[UiContribution, ...]


def _validate(contribution: UiContribution, plugin_name: str) -> None:
    where = f"{contribution.id!r} from {plugin_name}"
    if contribution.kind not in _KINDS:
        raise AgentConfigError(
            f"UI contribution {where} has kind {contribution.kind!r}; "
            "plugins contribute a module, a preset or a settings_section"
        )
    if contribution.kind == "module":
        if contribution.slot is None or contribution.slot not in SLOTS:
            raise AgentConfigError(
                f"Module {where} needs a slot, one of {sorted(SLOTS)}; "
                f"got {contribution.slot!r}"
            )
        if contribution.provider is None:
            raise AgentConfigError(f"Module {where} requires a provider")
    elif contribution.kind == "preset":
        prompt = contribution.prompt
        if not prompt or len(prompt) > PRESET_PROMPT_MAX:
            raise AgentConfigError(
                f"Preset {where} needs a prompt of 1 to {PRESET_PROMPT_MAX} characters"
            )
        if len(contribution.label) > PRESET_LABEL_MAX:
            raise AgentConfigError(
                f"Preset {where} has a label over {PRESET_LABEL_MAX} characters"
            )
    elif contribution.settings_operation_id is None:
        raise AgentConfigError(
            f"Settings section {where} requires settings_operation_id"
        )


def collect_ui_contributions(plugins: list) -> UiManifest:
    """Merge plugin UI contributions; raise AgentConfigError on conflicts."""
    seen_ids: set[str] = set()
    modules: list[UiContribution] = []
    presets: list[UiContribution] = []
    settings_sections: list[UiContribution] = []

    for plugin in plugins:
        plugin_name = type(plugin).__name__
        contributions = list(plugin.ui_contributions())
        if contributions:
            log.info(
                "plugin_ui_contributions_registered",
                plugin=plugin_name,
                modules=[c.id for c in contributions if c.kind == "module"],
                presets=[c.id for c in contributions if c.kind == "preset"],
                settings=[c.id for c in contributions if c.kind == "settings_section"],
            )
        for contribution in contributions:
            if contribution.id in seen_ids:
                raise AgentConfigError(
                    f"Duplicate UI contribution id {contribution.id!r} "
                    f"contributed by {plugin_name}"
                )
            seen_ids.add(contribution.id)
            _validate(contribution, plugin_name)
            {"module": modules, "preset": presets, "settings_section": settings_sections}[
                contribution.kind
            ].append(contribution)

    def _sort_key(contribution: UiContribution) -> tuple[int, str]:
        return (contribution.priority, contribution.id)

    return UiManifest(
        modules=tuple(sorted(modules, key=_sort_key)),
        presets=tuple(sorted(presets, key=_sort_key)),
        settings_sections=tuple(sorted(settings_sections, key=_sort_key)),
    )


def filter_ui_manifest_by_openapi(
    manifest: UiManifest,
    operation_ids: frozenset[str],
) -> UiManifest:
    """Drop settings sections whose operation IDs are missing from OpenAPI."""
    dropped: list[str] = []

    def _valid(item: UiContribution) -> bool:
        op = item.settings_operation_id
        if op is not None and op in operation_ids:
            return True
        log.warning(
            "ui_manifest_unknown_operation_id",
            contribution_id=item.id,
            plugin=item.plugin,
            operation_id=op,
            kind="settings_section",
        )
        dropped.append(item.id)
        return False

    filtered = UiManifest(
        modules=manifest.modules,
        presets=manifest.presets,
        settings_sections=tuple(i for i in manifest.settings_sections if _valid(i)),
    )
    if dropped:
        log.info(
            "ui_manifest_filtered",
            dropped_settings=dropped,
            settings_remaining=len(filtered.settings_sections),
        )
    return filtered


def get_module(manifest: UiManifest, module_id: str) -> UiContribution | None:
    return next((m for m in manifest.modules if m.id == module_id), None)


async def request_module_refresh(interface: Any, module_id: str) -> None:
    """Ask the client to refetch `module_id`. A failure is logged, never raised."""
    try:
        await interface.send_refresh(f"module:{module_id}")
    except Exception as exc:  # noqa: BLE001 — a refresh is a hint, never fatal
        log.warning("module_refresh_failed", module_id=module_id, error=str(exc))
