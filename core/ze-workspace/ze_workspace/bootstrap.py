from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ze_logging import get_logger

from ze_workspace.client import WorkspaceClient
from ze_workspace.gate import WorkspaceGate
from ze_workspace.store import PostgresWorkspaceStore, WorkspaceStore

log = get_logger(__name__)


@dataclass
class WorkspaceStack:
    client: WorkspaceClient
    store: PostgresWorkspaceStore
    gate: WorkspaceGate
    deps: dict[type, Any] = field(default_factory=dict)


def build_workspace_stack(shared: Any, settings: Any) -> WorkspaceStack:
    import ze_workspace.tools  # noqa: F401

    workspace_cfg = {}
    config = getattr(settings, "config", {}) or {}
    if hasattr(config, "get"):
        workspace_cfg = config.get("workspace", {}) or {}

    timeout = int(
        getattr(settings, "workspace_timeout_seconds", None)
        or workspace_cfg.get("run_timeout_seconds")
        or 120
    )
    client = WorkspaceClient(
        base_url=getattr(
            settings, "workspace_service_url", "http://ze-workspace.internal:8080"
        ),
        token=getattr(settings, "workspace_api_token", "") or "",
        timeout=timeout,
    )
    store = PostgresWorkspaceStore(pool=shared.pool)
    gate = WorkspaceGate()

    ze_workspace.tools.configure(
        client=client,
        gate=gate,
        store=store,
        settings=settings,
    )

    deps: dict[type, Any] = {
        WorkspaceClient: client,
        WorkspaceGate: gate,
        WorkspaceStore: store,
        PostgresWorkspaceStore: store,
    }
    log.info("workspace_stack_ready", url=client._base_url)
    return WorkspaceStack(client=client, store=store, gate=gate, deps=deps)
