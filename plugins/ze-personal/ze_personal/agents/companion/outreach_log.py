from typing import Protocol
from uuid import UUID


class OutreachLog(Protocol):
    """The campaign store the companion logs outreach events to; ze-prospecting provides it."""

    async def get_latest_outreach_id(self, contact_id: UUID) -> UUID | None: ...

    async def log_outreach_event(
        self,
        outreach_id: UUID,
        status: str,
        notes: str,
        ts_column: str | None,
    ) -> None: ...
