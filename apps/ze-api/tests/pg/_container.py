import atexit
import subprocess
import time
from dataclasses import dataclass

IMAGE = "pgvector/pgvector:pg16"
READY_TIMEOUT_SECONDS = 30


class PgHarnessError(RuntimeError):
    pass


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["docker", *args], capture_output=True, text=True, check=check, timeout=120
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PgHarnessError(
            "Docker is required for make test-pg (or set ZE_TEST_PG_URL)"
        ) from exc


@dataclass
class PgContainer:
    container_id: str
    asyncpg_url: str

    def stop(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.container_id], capture_output=True)


def start_container() -> PgContainer:
    _docker("info")
    run = _docker(
        "run",
        "-d",
        "--rm",
        "-p",
        "127.0.0.1::5432",
        "-e",
        "POSTGRES_USER=ze",
        "-e",
        "POSTGRES_PASSWORD=ze",
        "-e",
        "POSTGRES_DB=ze",
        IMAGE,
    )
    container_id = run.stdout.strip()
    handle = PgContainer(container_id, "")
    atexit.register(handle.stop)
    try:
        port_out = _docker("port", container_id, "5432").stdout.strip().splitlines()[0]
        port = port_out.rsplit(":", 1)[1]
        deadline = time.monotonic() + READY_TIMEOUT_SECONDS
        while True:
            ready = _docker(
                "exec", container_id, "pg_isready", "-U", "ze", "-d", "ze", check=False
            )
            if ready.returncode == 0:
                break
            if time.monotonic() > deadline:
                raise PgHarnessError("Postgres container did not become ready in 30s")
            time.sleep(0.5)
        # pg_isready can pass during the init-time restart; confirm with a query.
        while True:
            probe = _docker(
                "exec",
                container_id,
                "psql",
                "-U",
                "ze",
                "-d",
                "ze",
                "-tAc",
                "select 1",
                check=False,
            )
            if probe.returncode == 0:
                break
            if time.monotonic() > deadline:
                raise PgHarnessError("Postgres container did not accept queries in 30s")
            time.sleep(0.5)
    except BaseException:
        handle.stop()
        raise
    handle.asyncpg_url = f"postgresql://ze:ze@127.0.0.1:{port}/ze"
    return handle
