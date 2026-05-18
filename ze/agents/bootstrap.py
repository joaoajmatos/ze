from tavily import AsyncTavilyClient

from ze.agents.companion.agent import CompanionAgent
from ze.agents.registry import register_instance
from ze.agents.research.agent import ResearchAgent
from ze.openrouter.client import OpenRouterClient
from ze.settings import Settings


def bootstrap_agents(
    *,
    openrouter_client: OpenRouterClient,
    settings: Settings,
    tavily_client: AsyncTavilyClient | None = None,
) -> None:
    """Instantiate and register live agent instances (called once at app startup)."""
    if tavily_client is None:
        tavily_client = AsyncTavilyClient(api_key=settings.tavily_api_key)

    for name, cls, deps in (
        ("companion", CompanionAgent, (openrouter_client, settings)),
        ("research", ResearchAgent, (openrouter_client, tavily_client, settings)),
    ):
        agent_cfg = settings.agent_configs.get(name, {})
        if not agent_cfg.get("enabled", True):
            continue
        register_instance(name, cls(*deps))
