from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ze_logging import get_logger

from ze_workspace.client import WorkspaceClient
from ze_workspace.followthrough import RunWatcher
from ze_workspace.gate import WorkspaceGate
from ze_workspace.store import PostgresWorkspaceStore, WorkspaceStore
from ze_workspace.types import WorkspaceRun

log = get_logger(__name__)


class _NoopTurnStarter:
    """Stand-in TurnStarter until apps/ze-api wires the real invoke_raw_turn
    adapter (User Story 2, T023) — detach still happens, it just has no
    follow-up to deliver yet."""

    async def invoke_raw_turn(self, thread_id: str, prompt: str) -> None:
        log.info("workspace_followup_turn_starter_not_wired", thread_id=thread_id)


class _NoopPushSender:
    """Stand-in PushSender until apps/ze-api wires the real notifier adapter
    (User Story 2, T024)."""

    async def send_completion(self, run: WorkspaceRun) -> None:
        log.info("workspace_completion_push_sender_not_wired", run_id=str(run.id))


@dataclass
class WorkspaceStack:
    client: WorkspaceClient
    store: PostgresWorkspaceStore
    gate: WorkspaceGate
    run_watcher: RunWatcher
    deps: dict[type, Any] = field(default_factory=dict)


def build_workspace_stack(
    shared: Any,
    settings: Any,
    *,
    turn_starter: Any = None,
    push_sender: Any = None,
) -> WorkspaceStack:
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
    run_watcher = RunWatcher(
        store=store,
        turn_starter=turn_starter or _NoopTurnStarter(),
        push_sender=push_sender or _NoopPushSender(),
    )

    ze_workspace.tools.configure(
        client=client,
        gate=gate,
        store=store,
        settings=settings,
        run_watcher=run_watcher,
    )

    deps: dict[type, Any] = {
        WorkspaceClient: client,
        WorkspaceGate: gate,
        WorkspaceStore: store,
        PostgresWorkspaceStore: store,
        RunWatcher: run_watcher,
    }
    log.info("workspace_stack_ready", url=client._base_url)
    return WorkspaceStack(
        client=client, store=store, gate=gate, run_watcher=run_watcher, deps=deps
    )
