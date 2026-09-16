from uuid import uuid4

from ze_agents.label_match import Ambiguous, Miss, Unique, precise_label_match
from ze_worldstate.agents.agent import LoopsAgent, _AGENT_INSTRUCTIONS


def test_loops_agent_catalog():
    assert LoopsAgent.name == "loops"
    assert "list_open_loops" in LoopsAgent.tools
    assert "close_loop" in LoopsAgent.tools
    assert "drop_loop" in LoopsAgent.tools
    assert "forget_fact" not in LoopsAgent.tools


def test_instructions_require_unique_title_match():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "list_open_loops" in text
    assert "unique" in text
    assert "at most once" in text
    assert "never batch" in text


def test_two_job_titles_are_ambiguous_or_miss():
    result = precise_label_match(
        "forget the job",
        [(uuid4(), "Job switch worry"), (uuid4(), "Job interview loop")],
    )
    assert isinstance(result, (Ambiguous, Miss))


def test_unique_loop_title_matches():
    loop_id = uuid4()
    result = precise_label_match(
        "forget the job switch worry",
        [(loop_id, "Job switch worry"), (uuid4(), "Call mom")],
    )
    assert isinstance(result, Unique)
    assert result.item_id == loop_id


def test_forget_that_is_miss_not_a_write():
    result = precise_label_match(
        "forget that",
        [(uuid4(), "Job switch worry")],
    )
    assert isinstance(result, Miss)
