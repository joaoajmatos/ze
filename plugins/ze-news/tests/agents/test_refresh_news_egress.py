"""refresh_news force-fetches every feed, so a tool script must not loop over it (Phase 197)."""

from __future__ import annotations

from ze_agents.tool import get_tool

import ze_news.agents.tools  # noqa: F401


def test_refresh_news_is_kept_out_of_tool_scripts() -> None:
    spec = get_tool("refresh_news")
    assert spec.egress is True
