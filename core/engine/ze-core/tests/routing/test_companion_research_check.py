"""eval/calibration/companion_research_check.py is opt-in and offline-testable."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[5] / "eval/calibration/companion_research_check.py"
)


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("companion_research_check", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def test_without_live_it_exits_nonzero_and_makes_no_call(check, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["companion_research_check.py"])
    with (
        patch.object(check.httpx, "AsyncClient") as client,
        patch.object(check, "run_live") as live,
    ):
        assert check.main() != 0
    client.assert_not_called()
    live.assert_not_called()
    assert "--live" in capsys.readouterr().err


def test_it_selects_the_six_research_prompts(check):
    prompts = check.research_prompts()
    assert len(prompts) == 6
    assert all(p["gold_agent"] == "research" for p in prompts)


def test_summarise_reads_delegation_citations_and_usage(check):
    reply = {
        "agent_used": "companion",
        "response": "See https://example.com/a for details.",
        "tool_calls": [
            {"tool_name": "delegate_to_agent", "args": {"agent_name": "research"}}
        ],
    }
    row = check.summarise("x", reply, 4.2, (3, 0.012))
    assert row.delegated_to_research and row.cites_sources
    assert (row.llm_calls, row.cost_usd) == (3, 0.012)
    assert "companion" in check.format_table([row])


def test_summarise_without_delegation_or_sources(check):
    row = check.summarise(
        "y",
        {"agent_used": "companion", "response": "From memory.", "tool_calls": []},
        1.0,
        None,
    )
    assert not row.delegated_to_research and not row.cites_sources
    assert row.llm_calls is None
