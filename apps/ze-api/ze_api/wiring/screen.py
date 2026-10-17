"""Builds the screen resolver registry from every core factory and every plugin (phase 195)."""

from __future__ import annotations

from typing import Any

from ze_core.screen import ScreenResolverRegistry


def build_screen_registry(
    *,
    goal_store: Any,
    workflow_store: Any,
    held_write_store: Any,
    loop_store: Any,
    memory_store: Any,
    graph_store: Any,
    procedure_store: Any,
    skill_store: Any,
    workspace_store: Any,
    hypothesis_store: Any,
    notification_store: Any,
    plugins: list[Any],
) -> ScreenResolverRegistry:
    """A kind registered twice raises DuplicateScreenKindError, so a clash stops startup."""
    from ze_automation.screen_resolvers import build_screen_resolvers as automation
    from ze_correlation.screen_resolvers import build_screen_resolvers as correlation
    from ze_memory.screen_resolvers import build_screen_resolvers as memory
    from ze_proactive.screen_resolvers import build_screen_resolvers as proactive
    from ze_skills.screen_resolvers import build_screen_resolvers as skills
    from ze_workspace.screen_resolvers import build_screen_resolvers as workspace
    from ze_worldstate.screen_resolvers import build_screen_resolvers as worldstate

    registry = ScreenResolverRegistry()
    for resolver in [
        *automation(
            goal_store=goal_store,
            workflow_store=workflow_store,
            held_write_store=held_write_store,
        ),
        *worldstate(loop_store=loop_store),
        *memory(
            retriever=memory_store,
            graph_store=graph_store,
            procedure_store=procedure_store,
        ),
        *skills(skill_store=skill_store),
        *workspace(workspace_store=workspace_store),
        *correlation(hypothesis_store=hypothesis_store),
        *proactive(notification_store=notification_store),
        *(r for plugin in plugins for r in plugin.screen_resolvers()),
    ]:
        registry.register(resolver)
    return registry
