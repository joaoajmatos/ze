from __future__ import annotations

from pydantic import (
    BaseModel,
)


class AgentDayCount(BaseModel):
    agent: str
    count: int


class HeatmapDay(BaseModel):
    date: str
    total: int
    agents: list[AgentDayCount]


class ActivityHeatmapResponse(BaseModel):
    days: list[HeatmapDay]
    agents: list[str]
    start: str
    end: str
