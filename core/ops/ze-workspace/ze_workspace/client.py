from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import base64

import httpx

from ze_workspace.errors import (
    WorkspaceBusyError,
    WorkspaceFullError,
    WorkspaceNotFoundError,
    WorkspacePathError,
    WorkspaceUnavailableError,
)
from ze_workspace.types import (
    WorkspaceFile,
    WorkspaceFileTouch,
    WorkspaceRunResult,
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

    async def run(
        self,
        command: list[str],
        *,
        cwd: str = "",
        timeout_seconds: int = 120,
        stdin_b64: str | None = None,
        env: dict[str, str] | None = None,
    ) -> WorkspaceRunResult:
        data = await self._json(
            "POST",
            "/run",
            json_body={
                "command": command,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
                "stdin_b64": stdin_b64,
                "env": env or {},
            },
        )
        touches = [
            WorkspaceFileTouch(path=t["path"], op=t["op"])
            for t in data.get("files_touched") or []
        ]
        return WorkspaceRunResult(
            exit_code=int(data.get("exit_code") or 0),
            timed_out=bool(data.get("timed_out")),
            stdout_preview=str(data.get("stdout_preview") or ""),
            stderr_preview=str(data.get("stderr_preview") or ""),
            output_file_path=data.get("output_file_path"),
            files_touched=touches,
        )

    async def cancel(self) -> None:
        await self._json("POST", "/cancel")

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
            raise WorkspaceBusyError("workspace is occupied")
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
