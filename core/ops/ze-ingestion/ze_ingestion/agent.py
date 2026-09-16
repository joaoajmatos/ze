from __future__ import annotations

from ze_agents.base_agent import BaseAgent
from ze_agents.client import LLMClient
from ze_logging import get_logger
from ze_agents.registry import agent
from ze_agents.tool import ToolAccess, tool
from ze_agents.types import AgentContext, AgentResult, Intent, Mode

log = get_logger(__name__)

_AGENT_INSTRUCTIONS = """\
You are Ze's ingestion assistant. When the user sends a URL, file, or block of
text to ingest, extract it and run the ingestion pipeline.

Use ingest_url for URLs and ingest_text for raw text or already-extracted file
content. Confirm ingest/extraction: content type, number of facts extracted, and
the summary. That is archive extraction via MemorySink, not remember_fact.
Never say you remembered the file or that the remember tool stored it.
If ingest fails, do not claim ingest or remember success.
"""

_pipeline = None  # injected at container wiring time


def _set_pipeline(pipeline: object) -> None:
    global _pipeline
    _pipeline = pipeline


@tool(
    access=ToolAccess.WRITE,
    description="Fetch, process, and ingest content at the given URL (extraction, not remember_fact).",
)
async def ingest_url(url: str) -> dict:
    if _pipeline is None:
        return {"error": "Ingestion pipeline not available"}
    from ze_ingestion.types import IngestionRequest

    result = await _pipeline.ingest(IngestionRequest(url=url))  # type: ignore[union-attr]
    return {
        "ingestion_id": result.ingestion_id,
        "content_type": result.content_type.value,
        "summary": result.summary,
        "facts_count": result.facts_count,
        "entities_count": result.entities_count,
        "tags": result.tags,
    }


@tool(
    access=ToolAccess.WRITE,
    description="Ingest raw text or pre-extracted document content (extraction, not remember_fact).",
)
async def ingest_text(text: str, label: str = "") -> dict:
    if _pipeline is None:
        return {"error": "Ingestion pipeline not available"}
    from ze_ingestion.types import IngestionRequest

    result = await _pipeline.ingest(  # type: ignore[union-attr]
        IngestionRequest(
            file_bytes=text.encode(),
            mime_type="text/plain",
            label=label or None,
        )
    )
    return {
        "ingestion_id": result.ingestion_id,
        "content_type": result.content_type.value,
        "summary": result.summary,
        "facts_count": result.facts_count,
        "entities_count": result.entities_count,
        "tags": result.tags,
    }


@agent
class IngestionAgent(BaseAgent):
    name = "ingestion"
    display_name = "Content ingestion"
    description = (
        "Ingest external content — URLs, PDFs, videos, audio — via the ingestion pipeline"
    )
    model = "anthropic/claude-sonnet-4-5"
    timeout = 120
    intents = {
        "write": Intent(Mode.AUTONOMOUS, "Ingest content via the extraction pipeline."),
    }
    default_mode = Mode.AUTONOMOUS
    tools = ["ingest_url", "ingest_text"]

    def __init__(self, openrouter_client: LLMClient) -> None:
        self._client = openrouter_client

    async def run(self, ctx: AgentContext) -> AgentResult:
        await self.emit(ctx, "ingestion.starting")
        system = self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx)
        response, loop_tool_calls = await self.agentic_loop(
            ctx,
            client=self._client,
            messages=list(ctx.messages),
            system=system,
        )
        return AgentResult(
            agent=self.name,
            response=response,
            tool_calls=loop_tool_calls,
        )
