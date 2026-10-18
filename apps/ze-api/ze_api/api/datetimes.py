from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException


def require_aware(**values: datetime | None) -> None:
    """Reject a naive datetime query value: Postgres would read it in the session zone."""
    for name, value in values.items():
        if value is not None and value.tzinfo is None:
            raise HTTPException(
                status_code=422,
                detail=f"{name} must include a timezone offset (e.g. 2026-10-01T00:00:00Z)",
            )
