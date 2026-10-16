"""Opt-in live check: what happens when research prompts reach Ze (phase 167, option E input).

Sends the research prompts of eval/calibration/routing_holdout.jsonl to a running
`make dev-eval` backend through /eval/chat (the entry point eval/run.py uses) and
prints, per prompt: which agent answered, whether it delegated to research, the LLM
call count, cost, wall time and whether the reply cites sources. It costs credits and
never runs without --live. It informs the "companion as front door" question; it does
not gate anything.

Environment: ZE_EVAL_URL (default http://localhost:8000), ZE_API_KEY, DATABASE_URL.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

HOLDOUT = Path(__file__).with_name("routing_holdout.jsonl")
URL_RE = re.compile(r"https?://\S+")
DELEGATE_TOOL = "delegate_to_agent"
COST_QUERY = """
SELECT COUNT(*)::int AS calls, COALESCE(SUM(cost_usd), 0)::float AS cost
FROM llm_cost_log WHERE session_id = ANY($1::text[])
"""


@dataclass
class CheckRow:
    id: str
    agent: str | None
    delegated_to_research: bool
    llm_calls: int | None
    cost_usd: float | None
    wall_s: float
    cites_sources: bool
    error: str | None = None


def research_prompts(path: Path = HOLDOUT) -> list[dict[str, Any]]:
    rows = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]
    return [r for r in rows if r["gold_agent"] == "research" and not r["gold_multi"]]


def delegated_to_research(tool_calls: list[dict[str, Any]]) -> bool:
    return any(
        tc.get("tool_name") == DELEGATE_TOOL
        and (tc.get("args") or {}).get("agent_name") == "research"
        for tc in tool_calls
    )


def cites_sources(response: str | None) -> bool:
    return bool(response and URL_RE.search(response))


def summarise(
    row_id: str, reply: dict[str, Any], wall_s: float, usage: tuple[int, float] | None
) -> CheckRow:
    calls, cost = usage if usage else (None, None)
    return CheckRow(
        id=row_id,
        agent=reply.get("agent_used"),
        delegated_to_research=delegated_to_research(reply.get("tool_calls") or []),
        llm_calls=calls,
        cost_usd=cost,
        wall_s=wall_s,
        cites_sources=cites_sources(reply.get("response")),
        error=reply.get("error"),
    )


def format_table(rows: list[CheckRow]) -> str:
    lines = [
        f"{'prompt id':<28} {'agent':<12} {'delegated':<10} {'calls':>5} "
        f"{'cost':>9} {'wall':>7}  cited"
    ]
    for r in rows:
        calls = "-" if r.llm_calls is None else str(r.llm_calls)
        cost = "-" if r.cost_usd is None else f"${r.cost_usd:.4f}"
        lines.append(
            f"{r.id:<28} {str(r.agent):<12} {('yes' if r.delegated_to_research else 'no'):<10} "
            f"{calls:>5} {cost:>9} {r.wall_s:>6.1f}s  {'yes' if r.cites_sources else 'no'}"
            + (f"  ERROR {r.error}" if r.error else "")
        )
    return "\n".join(lines)


async def usage_for(session_id: str) -> tuple[int, float] | None:
    import asyncpg

    url = os.environ.get("DATABASE_URL", "postgresql://ze:ze@localhost:5432/ze")
    try:
        conn = await asyncpg.connect(url)
    except Exception:
        return None
    try:
        row = await conn.fetchrow(COST_QUERY, [session_id, f"eval-{session_id}"])
        return (row["calls"], row["cost"]) if row else None
    except Exception:
        return None
    finally:
        await conn.close()


async def run_live() -> list[CheckRow]:
    base = os.environ.get("ZE_EVAL_URL", "http://localhost:8000").rstrip("/")
    key = os.environ.get("ZE_API_KEY", "")
    rows: list[CheckRow] = []
    async with httpx.AsyncClient(timeout=180.0) as client:
        for prompt in research_prompts():
            session_id = f"companion-check-{uuid.uuid4().hex[:8]}"
            started = time.monotonic()
            resp = await client.post(
                f"{base}/eval/chat",
                json={"prompt": prompt["prompt"], "session_id": session_id},
                headers={"Authorization": f"Bearer {key}"},
            )
            resp.raise_for_status()
            wall = time.monotonic() - started
            rows.append(
                summarise(prompt["id"], resp.json(), wall, await usage_for(session_id))
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--live", action="store_true", help="required: this run costs credits"
    )
    args = parser.parse_args()
    if not args.live:
        print(
            "Refusing to run: pass --live (needs `make dev-eval` and costs credits).",
            file=sys.stderr,
        )
        return 2
    print(format_table(asyncio.run(run_live())))
    print(
        "\nNote: cost_usd is backfilled by the reconciler (up to 15 min); '-' or 0 "
        "means not yet known."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
