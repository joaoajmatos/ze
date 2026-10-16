from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProactiveJob(Protocol):
    job_id: str

    async def run(self) -> None: ...


def proactive_job(cls: type) -> type:
    """Mark a class as a proactive job. The class must define a job_id."""
    if not hasattr(cls, "job_id"):
        raise TypeError(f"{cls.__name__} must define a job_id class attribute")
    return cls
