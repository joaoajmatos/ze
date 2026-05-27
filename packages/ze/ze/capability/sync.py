"""Agent registration for the capability gate (Phase 7 — @agent on classes)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ze.settings import Settings


def sync_gate_registry(settings: Settings) -> None:
    """Import agent modules; @agent registers capability metadata in ze-core."""
    from ze.agents.bootstrap import _import_agent_modules

    _import_agent_modules()
