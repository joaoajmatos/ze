import os
import stat
import subprocess
import sys
from pathlib import Path

PG_DIR = Path(__file__).parent / "pg"
API_ROOT = Path(__file__).parent.parent


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_pg_tests_skip_without_docker(tmp_path: Path) -> None:
    marker = tmp_path / "docker-called"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n")
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)

    env = {k: v for k, v in os.environ.items() if not k.startswith("ZE_TEST_PG")}
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    collect = _run(["--collect-only", "-q", str(PG_DIR)], env)
    assert collect.returncode == 0, collect.stdout + collect.stderr

    run = _run(["-q", str(PG_DIR)], env)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "skipped" in run.stdout
    assert not marker.exists()
