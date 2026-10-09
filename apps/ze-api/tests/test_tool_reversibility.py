"""Every registered WRITE tool declares reversibility (Phase 165, FR-014)."""

from __future__ import annotations

from importlib.metadata import entry_points

from ze_agents.bootstrap import reload_agent_modules
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, registered_tools, validate_tool_declarations

from tests.support.agent_modules import ALL_AGENT_MODULE_PATHS

_CORE_TOOL_MODULES = [
    "ze_calendar.agents.calendar.tools",
    "ze_calendar.agents.reminders.tools",
    "ze_finance.agents.finance.tools",
    "ze_workspace.tools",
    "ze_ingestion.agent",
    "ze_worldstate.agents.tools",
]


def _load_all_tool_modules() -> None:
    paths = set(ALL_AGENT_MODULE_PATHS) | set(_CORE_TOOL_MODULES)
    for ep in entry_points(group="ze.plugins"):
        plugin_cls = ep.load()
        plugin = object.__new__(plugin_cls)
        plugin._enabled = True  # NewsPlugin gates its module list on config
        paths.update(plugin.agent_module_paths())
    reload_agent_modules(sorted(paths))


def test_every_write_tool_declares_reversibility() -> None:
    _load_all_tool_modules()
    writes = {
        name: spec
        for name, spec in registered_tools().items()
        if spec.access is ToolAccess.WRITE
    }
    assert len(writes) >= 40, "plugin tool modules did not load"
    undeclared = sorted(n for n, s in writes.items() if s.reversibility is None)
    assert undeclared == []
    for name, spec in writes.items():
        assert spec.effect_phrase, f"{name} has no effect_phrase"
        if spec.reversibility is ToolReversibility.REVERSIBLE:
            assert spec.undo_tool and spec.undo_note, name


def test_read_tools_declare_nothing() -> None:
    _load_all_tool_modules()
    for name, spec in registered_tools().items():
        if spec.access is ToolAccess.READ:
            assert spec.reversibility is None, name


def test_undo_tools_resolve() -> None:
    _load_all_tool_modules()
    validate_tool_declarations()
