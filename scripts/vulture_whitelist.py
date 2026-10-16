"""Vulture whitelist for `make deadcode`.

Vulture reads this file as data. Each `_.name` below counts as a use of `name`,
so a framework or entry-point name that nothing in the repo calls directly stops
showing up as dead code. The file never runs.

Only add a name when a framework, an entry point, or a protocol calls it by name.
Never add a name because it looks dead: that hides a real finding. A whitelisted
name is hidden everywhere, so keep entries specific.

Decorated functions need no entry. The Makefile passes `--ignore-decorators` for
`@tool`, `@agent`, `@render_tool`, `@mcp.tool`, `@proactive_job`, `@pytest.fixture`,
`@router.*`, `@app.*`, `@field_validator`, `@model_validator` and `@abstractmethod`.
Field and key false positives (Pydantic response models, LangGraph state keys,
serialized component descriptors) are filtered by path in the Makefile.
"""

from unittest.mock import MagicMock

_ = MagicMock()

# ZePlugin entry points (`[project.entry-points."ze.plugins"]`): loaded by name.
_.CalendarPlugin
_.FinancePlugin
_.MessengerPlugin
_.NewsPlugin
_.PersonalPlugin
_.ProspectingPlugin

# ZePlugin hooks: the container and the bootstrapper call these on every plugin.
_.agent_deps
_.agent_module_paths
_.agents
_.bundled_skill_paths
_.channels
_.checkpoint_serde_modules
_.configurable_services
_.graph_edges
_.graph_nodes
_.jobs
_.locale_data
_.memory_policies
_.migrations_path
_.onboarding
_.pre_route_node
_.rest_routes
_.rest_stores
_.shutdown
_.signal_sources
_.startup
_.state_extensions
_.ui_contributions
_.webhook_handlers

# HarnessHook hooks: the agentic loop calls them on every registered hook.
_.check_call
_.on_loop_end
_.on_loop_start
_.on_tool_end
_.on_tool_start

# Alembic migration modules: the runner reads these module attributes.
_.upgrade
_.downgrade
_.revision
_.down_revision
_.branch_labels
_.depends_on

# Pydantic settings and models.
_.model_config

# Standard-library and third-party override points.
_.handle_data  # html.parser.HTMLParser
_.row_factory  # sqlite3.Connection
_.__signature__  # inspect reads it to build the schema
_.writable  # file protocol: the tee stream handed to logging must answer it

# pytest hook (`pytest_*` functions are collected by name).
_.pytest_collection_modifyitems
