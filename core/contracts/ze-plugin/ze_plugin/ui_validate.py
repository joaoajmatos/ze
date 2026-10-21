from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ze_agents.claims import ClaimKind, Provenance
from ze_agents.errors import InvalidComponentError
from ze_agents.registry import get_registered_agents

__all__ = [
    "PLUGIN_CARD_INTENTS",
    "PLUGIN_CLAIM_KINDS",
    "PLUGIN_CLAIM_SUBJECTS",
    "plugin_agent_tools",
    "validate_plugin_tree",
]

# A plugin may state what it knows, never what Ze has decided: priority, action
# and feedback records belong to core, and so do the records behind loops,
# goals, workflows and held writes.
PLUGIN_CLAIM_KINDS = frozenset(
    {
        ClaimKind.IDENTITY.value,
        ClaimKind.FACT.value,
        ClaimKind.INFERENCE.value,
        ClaimKind.SUSPICION.value,
    }
)
PLUGIN_CLAIM_SUBJECTS = frozenset({"fact", "person"})
PLUGIN_CARD_INTENTS = frozenset({"open"})
_PROVENANCES = frozenset(p.value for p in Provenance)


def plugin_agent_tools(plugin: Any) -> dict[str, frozenset[str]]:
    """The agents a plugin registered, by name, each with its tool names."""
    prefixes = tuple(plugin.agent_module_paths())
    if not prefixes:
        return {}
    return {
        name: frozenset(cls.tools)
        for name, cls in get_registered_agents().items()
        if cls.__module__.startswith(prefixes)
    }


def _walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def validate_plugin_tree(plugin: Any, components: list[dict[str, Any]]) -> None:
    """Refuse a plugin view that borrows another owner's powers.

    Every tool action must name an agent this plugin registered and one of that
    agent's tools. Every claim posture must use a kind and subject a plugin may
    state and a source from the shared provenance vocabulary. Raises
    InvalidComponentError on the first violation.
    """
    agents = plugin_agent_tools(plugin)
    for node in _walk(components):
        if node.get("kind") == "tool":
            owner, tool = node.get("owner"), node.get("tool")
            if owner not in agents or tool not in agents[owner]:
                raise InvalidComponentError(
                    f"tool action {owner!r}.{tool!r} is not an agent tool of this plugin"
                )
        claim = node.get("claim")
        if isinstance(claim, dict):
            _check_claim(claim)
        intent = node.get("intent")
        if intent is not None and "ref_id" in node and intent not in PLUGIN_CARD_INTENTS:
            raise InvalidComponentError(
                f"card action intent {intent!r} is not available to plugin views"
            )


def _check_claim(claim: dict[str, Any]) -> None:
    kind = claim.get("kind")
    if kind is not None and kind not in PLUGIN_CLAIM_KINDS:
        raise InvalidComponentError(f"claim kind {kind!r} is not licensed for plugins")
    if claim.get("subject") not in PLUGIN_CLAIM_SUBJECTS:
        raise InvalidComponentError(
            f"claim subject {claim.get('subject')!r} is not licensed for plugins"
        )
    source = claim.get("source")
    if source is not None and source not in _PROVENANCES:
        raise InvalidComponentError(
            f"claim source {source!r} is not a shared provenance"
        )
