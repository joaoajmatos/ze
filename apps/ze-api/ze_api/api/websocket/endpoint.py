from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from ze_api.api.websocket.commands import handle_command
from ze_api.api.websocket.component_submit import handle_component_submit
from ze_api.api.websocket.confirmation import handle_confirm
from ze_api.api.websocket.goal_actions import handle_action
from ze_api.api.websocket.connection import ConnectionManager
from ze_api.api.websocket.onboarding import send_onboarding_view
from ze_api.api.websocket.turns import handle_message
from ze_logging import get_logger

log = get_logger(__name__)


def _track_gate(
    pending_configs: dict[str, dict],
    thread_pending_requests: dict[str, set[str]],
    request_id: str,
    thread_id: str,
    config: dict,
) -> None:
    pending_configs[request_id] = config
    thread_pending_requests.setdefault(thread_id, set()).add(request_id)


def _untrack_gate(
    pending_configs: dict[str, dict],
    thread_pending_requests: dict[str, set[str]],
    request_id: str,
    thread_id: str,
) -> None:
    pending_configs.pop(request_id, None)
    ids = thread_pending_requests.get(thread_id)
    if ids is not None:
        ids.discard(request_id)
        if not ids:
            thread_pending_requests.pop(thread_id, None)


async def websocket_endpoint(
    ws: WebSocket,
    token: str | None = None,
) -> None:
    settings = ws.app.state.settings
    api_key: str = settings.ze_api_key

    auth_header = ws.headers.get("Authorization", "")
    bearer = (
        auth_header.removeprefix("Bearer ").strip()
        if auth_header.startswith("Bearer ")
        else ""
    )

    if bearer != api_key and token != api_key:
        await ws.close(code=4001)
        return

    await ws.accept()

    container = ws.app.state.container
    conn_mgr: ConnectionManager = container.connection_manager
    msg_store = container.message_store
    confirmation_store = container.confirmation_store
    session_store = container.session_store

    await conn_mgr.connect(ws, msg_store, confirmation_store)
    log.info("ws_connected")

    onboarding_cfg = settings.config.get("onboarding", {})
    if onboarding_cfg.get("enabled", True) and onboarding_cfg.get(
        "auto_start_on_empty_profile",
        True,
    ):
        try:
            view = await container.onboarding_coordinator.start_if_needed()
            if view is not None:
                await send_onboarding_view(conn_mgr, view)
        except Exception as exc:
            log.warning("ws_onboarding_autostart_failed", error=str(exc))

    # LangGraph configs for in-flight confirmations, keyed by request_id so a
    # second gate opened on the same thread before the first resolves can
    # never overwrite or be popped by the other's resolution/timeout.
    pending_configs: dict[str, dict] = {}
    # Derived index: thread_id -> {request_id, ...} of gates open on that thread.
    thread_pending_requests: dict[str, set[str]] = {}

    try:
        while True:
            try:
                data = await ws.receive_json()
            except WebSocketDisconnect:
                break

            frame_type = data.get("type")

            if frame_type == "ping":
                await ws.send_json({"type": "pong"})

            elif frame_type == "ack":
                ids: list[UUID] = []
                for raw in data.get("ids") or []:
                    if not raw:
                        continue
                    try:
                        ids.append(UUID(str(raw)))
                    except (TypeError, ValueError):
                        log.warning("ws_ack_invalid_id", id=raw)
                await msg_store.mark_read(ids)

            elif frame_type == "command":
                # Commands are not per-thread (they operate on global session state).
                # Pass the first pending config for compatibility with cancel command.
                first_pending = next(iter(pending_configs.values()), None)
                new_pending = await handle_command(
                    ws, data, container, conn_mgr, first_pending
                )
                if new_pending is None and first_pending is not None:
                    pending_configs.clear()
                    thread_pending_requests.clear()

            elif frame_type == "component_submit":
                thread_id = data.get("thread_id") or ""
                if not thread_id:
                    await ws.send_json(
                        {"type": "error", "detail": "thread_id required"}
                    )
                    continue
                if not conn_mgr.try_set_busy(thread_id):
                    await conn_mgr.send_frame(
                        {"type": "error", "detail": "busy"}, thread_id
                    )
                    continue
                try:
                    result = await handle_component_submit(
                        ws,
                        data,
                        container,
                        conn_mgr,
                        msg_store,
                        None,
                        confirmation_store=confirmation_store,
                        session_store=session_store,
                    )
                    if result is not None:
                        new_request_id, new_config = result
                        _track_gate(
                            pending_configs,
                            thread_pending_requests,
                            new_request_id,
                            thread_id,
                            new_config,
                        )
                finally:
                    conn_mgr.clear_busy(thread_id)

            elif frame_type == "confirm":
                thread_id = data.get("thread_id") or ""
                if not thread_id:
                    await ws.send_json(
                        {"type": "error", "detail": "thread_id required in confirm"}
                    )
                    continue
                request_id = data.get("id") or ""
                result = await handle_confirm(
                    ws,
                    data,
                    container,
                    conn_mgr,
                    pending_configs.get(request_id),
                    thread_id=thread_id,
                    confirmation_store=confirmation_store,
                    session_store=session_store,
                    msg_store=msg_store,
                )
                if request_id:
                    _untrack_gate(
                        pending_configs, thread_pending_requests, request_id, thread_id
                    )
                if result is not None:
                    new_request_id, new_config = result
                    _track_gate(
                        pending_configs,
                        thread_pending_requests,
                        new_request_id,
                        thread_id,
                        new_config,
                    )

            elif frame_type == "action":
                await handle_action(ws, data, container, conn_mgr)

            elif frame_type == "message":
                thread_id = data.get("thread_id") or ""
                if not thread_id:
                    await ws.send_json(
                        {"type": "error", "detail": "thread_id required"}
                    )
                    continue
                if not conn_mgr.try_set_busy(thread_id):
                    await conn_mgr.send_frame(
                        {"type": "error", "detail": "busy"}, thread_id
                    )
                    continue

                # Spawn a background task so the WS loop can immediately accept
                # messages for other threads while this LLM call is in progress.
                asyncio.create_task(
                    _run_message_task(
                        ws,
                        data,
                        container,
                        msg_store,
                        conn_mgr,
                        pending_configs,
                        thread_pending_requests,
                        thread_id,
                        confirmation_store=confirmation_store,
                        session_store=session_store,
                    )
                )

    except Exception as exc:
        log.exception("ws_handler_error", error=str(exc))
    finally:
        await conn_mgr.disconnect()
        log.info("ws_disconnected")


async def _run_message_task(
    ws: WebSocket,
    data: dict,
    container: object,
    msg_store: object,
    conn_mgr: ConnectionManager,
    pending_configs: dict[str, dict],
    thread_pending_requests: dict[str, set[str]],
    thread_id: str,
    *,
    confirmation_store: object | None,
    session_store: object | None,
) -> None:
    """Background task wrapper: runs handle_message and clears the busy flag."""
    try:
        result = await handle_message(
            ws,
            data,
            container,
            msg_store,
            conn_mgr,
            None,
            confirmation_store=confirmation_store,
            session_store=session_store,
        )
        if result is not None:
            new_request_id, new_config = result
            _track_gate(
                pending_configs,
                thread_pending_requests,
                new_request_id,
                thread_id,
                new_config,
            )
    except Exception as exc:
        log.exception("ws_message_task_error", thread_id=thread_id, error=str(exc))
        await conn_mgr.send_frame(
            {"type": "error", "detail": "Something went wrong."}, thread_id
        )
    finally:
        conn_mgr.clear_busy(thread_id)
