from fastapi import APIRouter, Depends, Query

from ze.api.dependencies import get_pool

router = APIRouter(tags=["costs"])

_VALID_GROUP_BY = {"flow_type", "agent", "model", "session_id"}


@router.get(
    "/summary",
    summary="Cost summary",
    description=(
        "Aggregate LLM token usage and cost grouped by flow_type, agent, model, or session_id. "
        "Ordered by total_tokens descending."
    ),
)
async def cost_summary(
    days: int = Query(default=30, ge=1, le=365, description="Lookback window in days"),
    group_by: str = Query(default="flow_type", description="Grouping dimension"),
    pool=Depends(get_pool),
) -> dict:
    if group_by not in _VALID_GROUP_BY:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"group_by must be one of {sorted(_VALID_GROUP_BY)}")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                {group_by}                   AS grp,
                COUNT(*)::int                AS calls,
                SUM(prompt_tokens)::int      AS prompt_tokens,
                SUM(completion_tokens)::int  AS completion_tokens,
                SUM(total_tokens)::int       AS total_tokens,
                SUM(cost_usd)                AS cost_usd
            FROM llm_cost_log
            WHERE created_at >= NOW() - ($1 * INTERVAL '1 day')
            GROUP BY {group_by}
            ORDER BY SUM(total_tokens) DESC
            """,
            days,
        )

        totals = await conn.fetchrow(
            """
            SELECT
                COUNT(*)::int       AS total_calls,
                SUM(total_tokens)   AS total_tokens,
                SUM(cost_usd)       AS total_cost_usd
            FROM llm_cost_log
            WHERE created_at >= NOW() - ($1 * INTERVAL '1 day')
            """,
            days,
        )

    buckets = [
        {
            "group": row["grp"],
            "calls": row["calls"],
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "total_tokens": row["total_tokens"],
            "cost_usd": float(row["cost_usd"]) if row["cost_usd"] is not None else None,
        }
        for row in rows
    ]

    return {
        "period_days": days,
        "group_by": group_by,
        "total_calls": totals["total_calls"] or 0,
        "total_tokens": int(totals["total_tokens"] or 0),
        "total_cost_usd": float(totals["total_cost_usd"]) if totals["total_cost_usd"] is not None else None,
        "buckets": buckets,
    }
