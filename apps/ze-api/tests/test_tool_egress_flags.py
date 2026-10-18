"""A READ tool that takes a caller-chosen URL or host declares `egress` (Phase 197, T028)."""

from __future__ import annotations

from importlib.metadata import entry_points

from ze_agents.bootstrap import reload_agent_modules
from ze_agents.tool import ToolAccess, registered_tools

from tests.support.agent_modules import ALL_AGENT_MODULE_PATHS

_EGRESS_PARAMS = frozenset({"url", "uri", "link", "host", "endpoint", "domain"})

# A READ tool with one of those parameters that does not reach out to a caller-chosen
# address. Each entry says why it is exempt.
_EGRESS_EXEMPT: dict[str, str] = {}


def _load_all_tool_modules() -> None:
    paths = set(ALL_AGENT_MODULE_PATHS)
    for ep in entry_points(group="ze.plugins"):
        plugin_cls = ep.load()
        plugin = object.__new__(plugin_cls)
        plugin._enabled = True  # NewsPlugin gates its module list on config
        paths.update(plugin.agent_module_paths())
    reload_agent_modules(sorted(paths))


def _parameter_names(spec) -> set[str]:
    properties = spec.llm_schema()["function"]["parameters"].get("properties", {})
    return set(properties)


def test_read_tools_with_a_url_like_parameter_declare_egress() -> None:
    _load_all_tool_modules()
    offenders = []
    for name, spec in registered_tools().items():
        if spec.access is not ToolAccess.READ or spec.egress:
            continue
        if name in _EGRESS_EXEMPT:
            continue
        if _parameter_names(spec) & _EGRESS_PARAMS:
            offenders.append(name)
    assert sorted(offenders) == []


def test_egress_exemptions_name_a_reason_and_a_real_read_tool() -> None:
    _load_all_tool_modules()
    tools = registered_tools()
    for name, reason in _EGRESS_EXEMPT.items():
        assert reason.strip(), name
        assert name in tools, name
        assert tools[name].access is ToolAccess.READ, name
        assert not tools[name].egress, name
