from __future__ import annotations

from ze_agents.tool import get_tool

import ze_browser.tool  # noqa: F401 — registers browser_extract


def test_browser_extract_takes_a_caller_chosen_url_and_declares_egress():
    assert get_tool("browser_extract").egress is True
