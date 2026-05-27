"""Re-export ze-core tool registry (Phase 7 migration)."""

import ze_core.orchestration.tool as _tool_mod
from ze_core.orchestration.tool import ToolAccess, ToolSpec, clear_tool_registry, get_tool, registered_tools, tool

# Tests introspect the registry dict directly.
_tool_registry = _tool_mod._tools

__all__ = [
    "ToolAccess",
    "ToolSpec",
    "clear_tool_registry",
    "get_tool",
    "registered_tools",
    "tool",
    "_tool_registry",
]
