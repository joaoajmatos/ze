import time

import structlog
from tavily import AsyncTavilyClient

from ze_core.orchestration.tool import ToolAccess, tool
from ze.agents.types import ToolCall

log = structlog.get_logger(__name__)


@tool(access=ToolAccess.READ, description="Search the web for current information via Tavily.")
async def web_search(
    query: str,
    client: AsyncTavilyClient,
    max_results: int = 5,
) -> ToolCall:
    start = time.monotonic()
    try:
        result = await client.search(query, max_results=max_results)
        duration_ms = int((time.monotonic() - start) * 1000)
        return ToolCall(
            tool_name="web_search",
            args={"query": query, "max_results": max_results},
            result=result,
            duration_ms=duration_ms,
            success=True,
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.warning("web_search_failed", query=query, error=str(exc))
        return ToolCall(
            tool_name="web_search",
            args={"query": query, "max_results": max_results},
            result=None,
            duration_ms=duration_ms,
            success=False,
            error=str(exc),
        )
