from ze.agents.types import ToolCall


def format_search_results(tool_call: ToolCall) -> str:
    """Convert a Tavily web_search ToolCall result into a compact text block for the LLM."""
    if not tool_call.success or not tool_call.result:
        return "[search failed — no results available]"

    results = tool_call.result.get("results", [])
    if not results:
        return "[no search results found]"

    lines: list[str] = []
    for r in results:
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        content = r.get("content", "").strip()
        lines.append(f"**{title}**\n{url}\n{content}")

    return "\n\n---\n\n".join(lines)
