"""Workspace sidecar control API."""

from __future__ import annotations

import base64
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

import supervisor

app = FastAPI(title="ze-workspace")

WORKSPACE_ROOT = supervisor.WORKSPACE_ROOT
STORAGE_CEILING = supervisor.STORAGE_CEILING
API_TOKEN = os.environ.get("WORKSPACE_API_TOKEN", "")


def _require_token(authorization: str | None = Header(default=None)) -> None:
    if not API_TOKEN:
        return
    expected = f"Bearer {API_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def err(status: int, error: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, **extra})


def resolve_path(rel: str) -> Path | JSONResponse:
    raw = (rel or "").strip()
    if raw.startswith("/") or raw.startswith("~"):
        return err(400, "outside_workspace")
    candidate = (WORKSPACE_ROOT / raw).resolve()
    root = WORKSPACE_ROOT.resolve()
    if candidate != root and not str(candidate).startswith(str(root) + os.sep):
        return err(400, "outside_workspace")
    return candidate


def suggested_path(rel: str) -> str:
    p = Path(rel)
    parent = p.parent
    stem = p.stem or "file"
    suffix = p.suffix
    n = 1
    while True:
        name = f"{stem}-{n}{suffix}"
        candidate = parent / name if str(parent) != "." else Path(name)
        if not (WORKSPACE_ROOT / candidate).exists():
            return str(candidate)
        n += 1


def _file_entry(path: Path) -> dict:
    st = path.stat()
    rel = str(path.relative_to(WORKSPACE_ROOT))
    return {
        "path": rel,
        "size": 0 if path.is_dir() else st.st_size,
        "modified_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        "is_dir": path.is_dir(),
    }


class PutBody(BaseModel):
    path: str
    content_b64: str
    overwrite: bool = False


class RunBody(BaseModel):
    command: list[str]
    cwd: str = ""
    timeout_seconds: int = supervisor.DEFAULT_TIMEOUT
    stdin_b64: str | None = None
    env: dict[str, str] = {}


@app.on_event("startup")
async def _startup() -> None:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    supervisor.apply_network_isolation()


@app.get("/health")
async def health():
    ok = WORKSPACE_ROOT.exists() and os.access(WORKSPACE_ROOT, os.W_OK)
    return {"ok": bool(ok)}


@app.get("/stat", dependencies=[Depends(_require_token)])
async def stat():
    return {
        "bytes_used": supervisor.bytes_used(),
        "bytes_ceiling": STORAGE_CEILING,
        "busy": supervisor.busy(),
        "workspace_root": str(WORKSPACE_ROOT),
    }


@app.get("/fs", dependencies=[Depends(_require_token)])
async def list_fs(path: str = Query(default="")):
    target = resolve_path(path)
    if isinstance(target, JSONResponse):
        return target
    if not target.exists():
        return err(404, "not_found")
    if not target.is_dir():
        return {"files": [_file_entry(target)]}
    files = [_file_entry(child) for child in sorted(target.iterdir())]
    return {"files": files}


@app.get("/fs/download", dependencies=[Depends(_require_token)])
async def download(path: str = Query()):
    target = resolve_path(path)
    if isinstance(target, JSONResponse):
        return target
    if not target.exists():
        return err(404, "not_found")
    if target.is_dir():
        return err(400, "is_directory")
    return Response(
        content=target.read_bytes(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
    )


def _write_bytes(rel: str, content: bytes, overwrite: bool) -> dict | JSONResponse:
    target = resolve_path(rel)
    if isinstance(target, JSONResponse):
        return target
    if target.exists() and not overwrite:
        return err(409, "exists", suggested_path=suggested_path(rel))
    if target.is_dir():
        return err(400, "is_directory")
    used = supervisor.bytes_used()
    existing = target.stat().st_size if target.exists() else 0
    if used - existing + len(content) > STORAGE_CEILING:
        return err(413, "full")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    uid, gid = supervisor._workspace_uids()
    if uid is not None:
        try:
            os.chown(target, uid, gid or -1)
        except OSError:
            pass
    return {"path": str(target.relative_to(WORKSPACE_ROOT)), "size": len(content)}


@app.put("/fs", dependencies=[Depends(_require_token)])
async def put_fs(body: PutBody):
    try:
        content = base64.b64decode(body.content_b64)
    except Exception:
        return err(400, "invalid_b64")
    return _write_bytes(body.path, content, body.overwrite)


@app.post("/fs/upload", dependencies=[Depends(_require_token)])
async def upload_fs(
    file: UploadFile = File(...),
    path: str = Form(default=""),
):
    rel = path or file.filename or "upload"
    content = await file.read()
    return _write_bytes(rel, content, overwrite=False)


@app.delete("/fs", dependencies=[Depends(_require_token)])
async def delete_fs(path: str = Query()):
    target = resolve_path(path)
    if isinstance(target, JSONResponse):
        return target
    if not target.exists():
        return err(404, "not_found")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"ok": True}


@app.post("/run", dependencies=[Depends(_require_token)])
async def run(body: RunBody):
    if not body.command:
        return err(400, "empty_command")
    stdin_bytes = base64.b64decode(body.stdin_b64) if body.stdin_b64 else None
    result = await supervisor.run_command(
        body.command,
        cwd=body.cwd,
        timeout_seconds=body.timeout_seconds or supervisor.DEFAULT_TIMEOUT,
        env=body.env,
        stdin_bytes=stdin_bytes,
    )
    if result.get("error") == "busy":
        return err(409, "busy")
    if result.get("error") == "outside_workspace":
        return err(400, "outside_workspace")
    result.pop("child_env", None)
    result.pop("status", None)
    result.pop("error", None)
    return result


@app.post("/cancel", dependencies=[Depends(_require_token)])
async def cancel():
    killed = await supervisor.cancel_run()
    if not killed:
        return err(404, "not_running")
    return {"ok": True}


@app.post("/reset", dependencies=[Depends(_require_token)])
async def reset():
    await supervisor.reset_workspace()
    return {"ok": True}
