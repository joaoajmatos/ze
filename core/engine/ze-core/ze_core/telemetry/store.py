from __future__ import annotations

from typing import Protocol, runtime_checkable

from ze_core.telemetry.types import CostRecord


@runtime_checkable
class CostStore(Protocol):
    async def write(self, rec: CostRecord) -> None: ...

    async def fetch_session_usage(self, session_id: str) -> list[dict]: ...

    async def fetch_daily_usage(self) -> list[dict]: ...
