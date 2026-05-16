from fastapi import APIRouter, Depends, HTTPException

from ze.api.dependencies import get_pool
from ze.api.schemas import FactReviewRequest

router = APIRouter(tags=["memory"])


@router.get("/facts")
async def list_facts(pool=Depends(get_pool)) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, key, value, agent, confidence, reviewed, contradicted, updated_at "
            "FROM user_facts ORDER BY updated_at DESC"
        )
    return [dict(r) for r in rows]


@router.post("/facts/review")
async def review_facts(body: FactReviewRequest, pool=Depends(get_pool)) -> list[dict]:
    updated: list[dict] = []
    async with pool.acquire() as conn:
        for action in body.actions:
            if action.action == "reject":
                await conn.execute(
                    "DELETE FROM user_facts WHERE id = $1", action.id
                )
            elif action.action == "confirm":
                row = await conn.fetchrow(
                    "UPDATE user_facts SET reviewed = true WHERE id = $1 RETURNING *",
                    action.id,
                )
                if row:
                    updated.append(dict(row))
            elif action.action == "edit":
                if action.value is None:
                    raise HTTPException(status_code=422, detail="value required for edit action")
                row = await conn.fetchrow(
                    "UPDATE user_facts SET value = $1, reviewed = true WHERE id = $2 RETURNING *",
                    action.value,
                    action.id,
                )
                if row:
                    updated.append(dict(row))
    return updated


@router.get("/digest")
async def memory_digest(pool=Depends(get_pool)) -> dict:
    async with pool.acquire() as conn:
        unreviewed = await conn.fetch(
            "SELECT id, key, value, agent FROM user_facts WHERE reviewed = false ORDER BY updated_at DESC"
        )
        contradicted = await conn.fetch(
            "SELECT id, key, value, agent FROM user_facts WHERE contradicted = true ORDER BY updated_at DESC"
        )
        episodes = await conn.fetch(
            "SELECT id, agent, summary, relevance, created_at FROM episodes ORDER BY created_at DESC LIMIT 10"
        )
    return {
        "unreviewed_facts": [dict(r) for r in unreviewed],
        "contradicted_facts": [dict(r) for r in contradicted],
        "recent_episodes": [dict(r) for r in episodes],
    }
