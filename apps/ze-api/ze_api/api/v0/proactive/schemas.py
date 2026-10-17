from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ProactiveJobRunItem(BaseModel):
    job_id: str
    last_started_at: datetime
    last_finished_at: datetime | None
    last_status: Literal["running", "ok", "error"]
