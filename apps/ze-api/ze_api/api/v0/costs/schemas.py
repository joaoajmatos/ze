from __future__ import annotations

from pydantic import (
    BaseModel,
)


class AgentCostBucket(BaseModel):
    usd: float
    tokens: int
    calls: int
    prompt_tokens: int
    completion_tokens: int


class DailyCostBucket(BaseModel):
    date: str
    usd: float
    calls: int


class CostAnomalyItem(BaseModel):
    agent: str
    run_cost_usd: float
    baseline_cost_usd: float
    multiplier: float
    session_id: str | None
    detected_at: str


class CostAnomaliesResponse(BaseModel):
    anomalies: list[CostAnomalyItem]
    period_days: int


class WebCostSummaryResponse(BaseModel):
    total_usd: float
    total_tokens: int
    total_calls: int
    by_agent: dict[str, AgentCostBucket]
    by_plugin: dict[str, AgentCostBucket]
    by_day: list[DailyCostBucket]
    period: str
