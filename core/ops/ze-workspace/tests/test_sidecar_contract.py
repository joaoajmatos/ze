"""Sidecar control-API contract via a fake supervisor (no Docker)."""

from __future__ import annotations

import os
from pathlib import Path

from ze_workspace.errors import (
    WorkspaceBusyError,
    WorkspaceFullError,
    WorkspacePathError,
)


class FakeSidecar:
    """In-process stand-in for sidecar/workspace — same error shapes as the contract."""

    def __init__(self, root: Path, ceiling: int = 1024) -> None:
        self.root = root
        self.ceiling = ceiling
        self.busy = False
        self.token = "supervisor-token"
        root.mkdir(parents=True, exist_ok=True)

    def resolve(self, rel: str) -> Path:
        raw = (rel or "").strip()
        if raw.startswith("/") or raw.startswith("~") or ".." in Path(raw).parts:
            raise WorkspacePathError("outside_workspace")
        candidate = (self.root / raw).resolve()
        if candidate != self.root and not str(candidate).startswith(
            str(self.root) + os.sep
        ):
            raise WorkspacePathError("outside_workspace")
        return candidate

    def list_dir(self, rel: str = "") -> list[str]:
        target = self.resolve(rel)
        if not target.exists():
            return []
        return sorted(p.name for p in target.iterdir())

    def write(self, rel: str, content: bytes) -> None:
        if self._used() + len(content) > self.ceiling:
            raise WorkspaceFullError("full")
        target = self.resolve(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def run(self, command: list[str], env: dict[str, str] | None = None) -> dict:
        if self.busy:
            raise WorkspaceBusyError("busy")
        child = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/workspace",
            "LANG": "C.UTF-8",
        }
        for key, value in (env or {}).items():
            upper = key.upper()
            if upper in {
                "DATABASE_URL",
                "OPENROUTER_API_KEY",
                "ZE_API_KEY",
                "WORKSPACE_API_TOKEN",
            }:
                continue
            if upper.endswith(("_SECRET", "_TOKEN", "_PASSWORD")):
                continue
            child[key] = value
        return {"exit_code": 0, "child_env": child}

    def _used(self) -> int:
        total = 0
        for dirpath, _dns, filenames in os.walk(self.root):
            for name in filenames:
                total += (Path(dirpath) / name).stat().st_size
        return total


def test_path_escape_refused(tmp_path: Path):
    sidecar = FakeSidecar(tmp_path / "ws")
    try:
        sidecar.resolve("../")
        raise AssertionError("expected outside_workspace")
    except WorkspacePathError as exc:
        assert "outside_workspace" in str(exc)


def test_child_env_lacks_token_and_secrets(tmp_path: Path):
    sidecar = FakeSidecar(tmp_path / "ws")
    result = sidecar.run(
        ["env"],
        env={
            "WORKSPACE_API_TOKEN": "leaked",
            "OPENROUTER_API_KEY": "sk-secret",
            "MY_PASSWORD": "nope",
            "NOTE": "ok",
        },
    )
    env = result["child_env"]
    assert "WORKSPACE_API_TOKEN" not in env
    assert "OPENROUTER_API_KEY" not in env
    assert "MY_PASSWORD" not in env
    assert env["NOTE"] == "ok"
    assert env["HOME"] == "/workspace"


def test_second_run_busy(tmp_path: Path):
    sidecar = FakeSidecar(tmp_path / "ws")
    sidecar.busy = True
    try:
        sidecar.run(["echo", "hi"])
        raise AssertionError("expected busy")
    except WorkspaceBusyError:
        pass


def test_ceiling_refuse_leaves_tree_unchanged(tmp_path: Path):
    sidecar = FakeSidecar(tmp_path / "ws", ceiling=10)
    sidecar.write("keep.txt", b"hello")
    before = sidecar.list_dir()
    try:
        sidecar.write("big.txt", b"this is way too big")
        raise AssertionError("expected full")
    except WorkspaceFullError:
        pass
    assert sidecar.list_dir() == before
    assert (sidecar.root / "big.txt").exists() is False
    assert (sidecar.root / "keep.txt").read_bytes() == b"hello"
