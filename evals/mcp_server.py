"""
Ze Eval MCP Server

Exposes Ze's eval endpoint as MCP tools so any LLM-powered IDE
(Claude Code, Cursor, Codex) can interactively send messages to Ze,
inspect routing decisions, and evaluate responses.

Configuration (via environment variables):
  ZE_EVAL_URL  — base URL of the Ze server (default: http://localhost:8000)
  ZE_API_KEY   — API key for the eval endpoint

Usage:
  uv run python evals/mcp_server.py

Add to Claude Code (.claude/settings.json):
  {
    "mcpServers": {
      "ze-eval": {
        "command": "uv",
        "args": ["run", "python", "evals/mcp_server.py"],
        "env": {
          "ZE_EVAL_URL": "http://localhost:8000",
          "ZE_API_KEY": "<your-key>"
        }
      }
    }
  }
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

_ZE_EVAL_URL = os.getenv("ZE_EVAL_URL", "http://localhost:8000")
_ZE_API_KEY = os.getenv("ZE_API_KEY", "")
_SCENARIOS_DIR = Path(__file__).parent / "scenarios"
_HEADERS = {"x-ze-api-key": _ZE_API_KEY}

mcp = FastMCP("Ze Eval")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_all_scenarios() -> list[dict]:
    scenarios: list[dict] = []
    for path in sorted(_SCENARIOS_DIR.glob("*.yaml")):
        import yaml  # noqa: PLC0415
        items = yaml.safe_load(path.read_text()) or []
        for item in items:
            item.setdefault("file", path.stem)
            scenarios.append(item)
    return scenarios


def _find_scenario(scenario_id: str) -> dict | None:
    for s in _load_all_scenarios():
        if s.get("id") == scenario_id:
            return s
    return None


async def _do_chat(prompt: str, session_id: str) -> dict:
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{_ZE_EVAL_URL}/eval/chat",
            json={"prompt": prompt, "session_id": session_id},
            headers=_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def ze_chat(prompt: str, session_id: str = "eval") -> str:
    """
    Send a message to Ze and receive its full response with routing metadata.

    Returns JSON with:
      - response: Ze's text response
      - agent_used: which agent handled the request (e.g. "companion", "research")
      - routing: { primary_agent, confidence, routing_method, is_compound, score_gap, raw_scores }
      - pending_confirmation: true if Ze would pause to ask the user for confirmation
      - error: error message if the graph failed

    Use session_id to simulate multi-turn conversations (same ID = shared history).
    Each unique session_id gets its own conversation thread.
    """
    result = await _do_chat(prompt, session_id)
    return json.dumps(result, indent=2)


@mcp.tool()
async def ze_list_scenarios(tag: str = "") -> str:
    """
    List all available test scenarios from evals/scenarios/.

    Returns a JSON array of scenario objects, each with:
      - id: unique identifier
      - prompt: the message that will be sent to Ze
      - description: what this scenario is testing
      - expected_agent: the agent Ze should route to (optional)
      - tags: list of category tags
      - criteria: list of evaluation rubric items (optional)

    Optionally filter by tag (e.g. "companion", "routing", "persona").
    """
    all_scenarios = _load_all_scenarios()
    if tag:
        all_scenarios = [s for s in all_scenarios if tag in s.get("tags", [])]
    return json.dumps(all_scenarios, indent=2)


@mcp.tool()
async def ze_run_scenario(scenario_id: str) -> str:
    """
    Run a named test scenario against Ze and return the result alongside the scenario definition.

    Returns JSON with:
      - scenario: the full scenario definition (prompt, expected_agent, criteria, etc.)
      - result: Ze's response and routing metadata
      - matches_expected_agent: true if Ze used the expected agent (null if no expectation set)

    You (the evaluator) should read the criteria and judge whether Ze's response passes.
    """
    scenario = _find_scenario(scenario_id)
    if scenario is None:
        return json.dumps({"error": f"Scenario '{scenario_id}' not found"})

    result = await _do_chat(scenario["prompt"], f"eval-{scenario_id}")

    matches = None
    if scenario.get("expected_agent") and result.get("agent_used"):
        matches = result["agent_used"] == scenario["expected_agent"]

    return json.dumps({
        "scenario": scenario,
        "result": result,
        "matches_expected_agent": matches,
    }, indent=2)


@mcp.tool()
async def ze_run_suite(tag: str = "") -> str:
    """
    Run all test scenarios (optionally filtered by tag) against Ze.

    Returns a JSON array of results, each with:
      - scenario: the scenario definition
      - result: Ze's response and routing metadata
      - matches_expected_agent: routing accuracy check

    Use this to get a broad picture of Ze's current behaviour before making changes,
    then run again after to detect regressions.
    """
    all_scenarios = _load_all_scenarios()
    if tag:
        all_scenarios = [s for s in all_scenarios if tag in s.get("tags", [])]

    results = []
    for scenario in all_scenarios:
        result = await _do_chat(scenario["prompt"], f"eval-{scenario['id']}")
        matches = None
        if scenario.get("expected_agent") and result.get("agent_used"):
            matches = result["agent_used"] == scenario["expected_agent"]
        results.append({
            "scenario": scenario,
            "result": result,
            "matches_expected_agent": matches,
        })

    summary = {
        "total": len(results),
        "routing_correct": sum(1 for r in results if r["matches_expected_agent"] is True),
        "routing_wrong": sum(1 for r in results if r["matches_expected_agent"] is False),
        "routing_unchecked": sum(1 for r in results if r["matches_expected_agent"] is None),
        "errors": sum(1 for r in results if r["result"].get("error")),
        "results": results,
    }
    return json.dumps(summary, indent=2)


if __name__ == "__main__":
    mcp.run()
