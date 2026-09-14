from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from uuid import UUID
import base64

import httpx

from ze_workspace.errors import (
    WorkspaceBusyError,
    WorkspaceFullError,
    WorkspaceNotFoundError,
    WorkspacePathError,
    WorkspaceRunAlreadyTerminalError,
    WorkspaceUnavailableError,
)
from ze_workspace.sanitize import redact
from ze_workspace.types import (
    JournalEventDTO,
    WorkspaceFile,
    WorkspaceFileTouch,
    WorkspaceRunStatusDTO,
    WorkspaceStat,
)


def _parse_dt(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def _files(payload: dict) -> list[WorkspaceFile]:
    result: list[WorkspaceFile] = []
    for item in payload.get("files") or []:
        result.append(
            WorkspaceFile(
                path=item["path"],
                size=int(item.get("size") or 0),
                modified_at=_parse_dt(item.get("modified_at")),
                is_dir=bool(item.get("is_dir")),
            )
        )
    return result


class WorkspaceClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",
        timeout: int = 120,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._client = httpx.AsyncClient(timeout=timeout)

    def _headers(self) -> dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    async def health(self) -> bool:
        try:
            resp = await self._client.get(f"{self._base_url}/health", timeout=5)
            if resp.status_code != 200:
                return False
            data = resp.json()
            return bool(data.get("ok") or data.get("status") == "ok")
        except Exception:
            return False

    async def stat(self) -> WorkspaceStat:
        data = await self._get_json("/stat")
        return WorkspaceStat(
            bytes_used=int(data.get("bytes_used") or 0),
            bytes_ceiling=int(data.get("bytes_ceiling") or 0),
            busy=bool(data.get("busy")),
            workspace_root=str(data.get("workspace_root") or "/workspace"),
            available=True,
        )

    async def list_dir(self, path: str = "") -> list[WorkspaceFile]:
        data = await self._get_json("/fs", params={"path": path})
        return _files(data)

    async def download(self, path: str) -> bytes:
        resp = await self._request(
            "GET", "/fs/download", params={"path": path}
        )
        return resp.content

    async def put(
        self,
        path: str,
        content: bytes,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        return await self._json(
            "PUT",
            "/fs",
            json_body={
                "path": path,
                "content_b64": base64.b64encode(content).decode("ascii"),
                "overwrite": overwrite,
            },
        )

    async def upload(self, path: str, content: bytes, filename: str) -> dict[str, Any]:
        try:
            resp = await self._client.post(
                f"{self._base_url}/fs/upload",
                headers=self._headers(),
                files={"file": (filename, content)},
                data={"path": path},
            )
        except httpx.TimeoutException as exc:
            raise WorkspaceUnavailableError(
                f"Workspace service timed out: {exc}"
            ) from exc
        except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            raise WorkspaceUnavailableError(
                f"Cannot reach workspace service: {exc}"
            ) from exc
        self._raise_for_status(resp)
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return {"path": path, "size": len(content)}

    async def delete(self, path: str) -> None:
        await self._request("DELETE", "/fs", params={"path": path})

    async def start_run(
        self,
        command: list[str],
        run_id: UUID,
        *,
        cwd: str = "",
        timeout_seconds: int = 120,
        stdin_b64: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """POSTs /run with id=run_id; returns as soon as the sidecar has
        recorded the run (FR-001 — does not wait for the process to exit).
        Raises WorkspaceBusyError on 409 (the one-slot invariant, backstop —
        tools.py checks list_in_progress() first so this is rarely hit)."""
        await self._json(
            "POST",
            "/run",
            json_body={
                "command": command,
                "id": str(run_id),
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
                "stdin_b64": stdin_b64,
                "env": env or {},
            },
        )

    async def get_run(self, run_id: UUID) -> WorkspaceRunStatusDTO | None:
        """GET /runs/{id}. Returns None on 404 (unknown or retention-evicted
        handle) rather than raising — callers (RunWatcher.reattach) treat
        that as "computer restarted and lost it" (Edge Case 3)."""
        try:
            data = await self._get_json(f"/runs/{run_id}")
        except WorkspaceNotFoundError:
            return None
        touches = [
            WorkspaceFileTouch(path=t["path"], op=t["op"])
            for t in data.get("files_touched") or []
        ]
        return WorkspaceRunStatusDTO(
            id=run_id,
            status=str(data.get("status") or "running"),
            exit_code=data.get("exit_code"),
            timed_out=bool(data.get("timed_out")),
            stdout_preview=redact(str(data.get("stdout_preview") or "")),
            stderr_preview=redact(str(data.get("stderr_preview") or "")),
            output_file_path=data.get("output_file_path"),
            files_touched=touches,
        )

    async def watch_run(self, run_id: UUID) -> AsyncIterator[JournalEventDTO]:
        """GET /runs/{id}/events as a streaming async generator — already-
        buffered events replay first, then live events follow, closing after
        the terminal `exit` event (FR-005). Redaction (FR-012) is applied
        here at the mind/client boundary, not inside the sidecar — the
        sidecar has no Ze package dependencies (Phase 115 isolation) and so
        cannot import ze_workspace.sanitize."""
        url = f"{self._base_url}/runs/{run_id}/events"
        try:
            async with self._client.stream(
                "GET", url, headers=self._headers()
            ) as resp:
                if resp.status_code == 404:
                    await resp.aread()
                    raise WorkspaceNotFoundError(f"workspace run {run_id} not found")
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise WorkspaceUnavailableError(
                        f"Workspace service error {resp.status_code}: "
                        f"{body[:200].decode('utf-8', errors='replace')}"
                    )
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    yield JournalEventDTO(
                        seq=int(data.get("seq") or 0),
                        type=str(data.get("type") or ""),
                        data=redact(str(data.get("data") or "")),
                        exit_code=data.get("exit_code"),
                        timed_out=data.get("timed_out"),
                    )
        except httpx.TimeoutException as exc:
            raise WorkspaceUnavailableError(
                f"Workspace service timed out: {exc}"
            ) from exc
        except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            raise WorkspaceUnavailableError(
                f"Cannot reach workspace service: {exc}"
            ) from exc

    async def cancel_run(self, run_id: UUID) -> None:
        """POST /runs/{id}/cancel. Raises WorkspaceNotFoundError (404) or
        WorkspaceRunAlreadyTerminalError (409)."""
        await self._json("POST", f"/runs/{run_id}/cancel")

    async def reset(self) -> None:
        await self._json("POST", "/reset")

    async def close(self) -> None:
        await self._client.aclose()

    async def _get_json(self, path: str, params: dict | None = None) -> dict:
        resp = await self._request("GET", path, params=params)
        return resp.json()

    async def _json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        resp = await self._request(
            method, path, json_body=json_body, params=params
        )
        if not resp.content:
            return {}
        return resp.json()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        try:
            resp = await self._client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers(),
                json=json_body,
                params=params,
            )
        except httpx.TimeoutException as exc:
            raise WorkspaceUnavailableError(
                f"Workspace service timed out: {exc}"
            ) from exc
        except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            raise WorkspaceUnavailableError(
                f"Cannot reach workspace service: {exc}"
            ) from exc
        self._raise_for_status(resp)
        return resp

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return
        payload: dict[str, Any] = {}
        try:
            payload = resp.json()
        except Exception:
            payload = {"error": resp.text[:200]}
        if "error" not in payload and isinstance(payload.get("detail"), dict):
            payload = payload["detail"]
        error = str(payload.get("error") or payload.get("detail") or "")
        if resp.status_code == 409 and error == "busy":
            running_id = payload.get("id")
            running_command = payload.get("command")
            raise WorkspaceBusyError(
                f"workspace is occupied by run {running_id}: {running_command}"
            )
        if resp.status_code == 409 and error == "already_terminal":
            raise WorkspaceRunAlreadyTerminalError(
                payload.get("status") or "already finished"
            )
        if resp.status_code in {409, 413} and error in {"full", "exists"}:
            if error == "full" or resp.status_code == 413:
                raise WorkspaceFullError("workspace storage ceiling would be exceeded")
            raise WorkspacePathError(
                payload.get("suggested_path") or "path already exists"
            )
        if resp.status_code == 400 or error == "outside_workspace":
            raise WorkspacePathError(error or "outside_workspace")
        if resp.status_code == 404:
            raise WorkspaceNotFoundError(error or "not found")
        if resp.status_code >= 500:
            raise WorkspaceUnavailableError(
                f"Workspace service error {resp.status_code}: {resp.text[:200]}"
            )
        raise WorkspaceUnavailableError(
            f"Workspace service error {resp.status_code}: {error or resp.text[:200]}"
        )
