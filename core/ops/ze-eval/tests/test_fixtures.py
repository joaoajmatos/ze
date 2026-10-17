import asyncio
from datetime import date

import pytest

from ze_eval import runner
from ze_eval.fixtures import KINDS, FixtureError, Fixtures, substitute
from ze_eval.judge import build_prompt
from ze_eval.scenario import describe_context

BINDINGS = {
    "wf": {"id": "11111111-1111-1111-1111-111111111111", "name": "Weekly report"}
}


def test_substitute_fills_nested_strings():
    out = substitute(
        {
            "subject": [
                {"kind": "workflow", "id": "{{wf.id}}", "label": "{{ wf.name }}"}
            ],
            "n": 3,
        },
        BINDINGS,
    )
    assert out == {
        "subject": [
            {"kind": "workflow", "id": BINDINGS["wf"]["id"], "label": "Weekly report"}
        ],
        "n": 3,
    }


def test_substitute_rejects_unknown_names_and_fields():
    with pytest.raises(FixtureError):
        substitute("{{nope.id}}", BINDINGS)
    with pytest.raises(FixtureError):
        substitute("{{wf.missing}}", BINDINGS)


def test_every_kind_declares_its_table_and_a_default_row():
    assert {
        "goal",
        "goal_gate",
        "workflow",
        "workflow_execution",
        "held_write",
        "loop",
        "entity",
        "fact",
        "procedure",
        "skill",
        "workspace_run",
        "hypothesis",
        "notification",
        "contact",
        "reminder",
        "news_article",
    } <= set(KINDS)
    for name, kind in KINDS.items():
        row = kind.defaults("Eval row")
        assert row, name
        assert kind.parent_column is None or kind.parent_column not in row, name


class _Conn:
    def __init__(self):
        self.sql: list[tuple[str, tuple]] = []
        self.closed = False

    async def fetchval(self, sql, *params):
        self.sql.append((sql, params))
        return f"id-{len(self.sql)}"

    async def execute(self, sql, *params):
        self.sql.append((sql, params))

    async def close(self):
        self.closed = True


def test_children_need_a_parent_naming_an_earlier_item():
    async def go():
        fixtures = Fixtures(_Conn())
        await fixtures._insert({"kind": "workflow_execution", "name": "run"})

    with pytest.raises(FixtureError, match="parent"):
        asyncio.run(go())


def test_inserts_bind_names_and_delete_newest_first():
    async def go():
        conn = _Conn()
        fixtures = Fixtures(conn)
        await fixtures._insert(
            {"kind": "workflow", "name": "wf", "fields": {"name": "Weekly report"}}
        )
        await fixtures._insert(
            {"kind": "workflow_execution", "name": "run", "parent": "wf"}
        )
        assert fixtures.bindings["wf"]["name"] == "Weekly report"
        assert (
            conn.sql[1][1][-1] == fixtures.bindings["wf"]["id"]
            or fixtures.bindings["wf"]["id"] in conn.sql[1][1]
        )
        await fixtures.delete()
        return conn

    conn = asyncio.run(go())
    deletes = [sql for sql, _ in conn.sql if sql.startswith("DELETE")]
    assert deletes[0].startswith("DELETE FROM workflow_executions") and deletes[
        1
    ].startswith("DELETE FROM workflows")
    assert conn.closed


def test_names_are_unique_and_kinds_known():
    async def go(item):
        fixtures = Fixtures(_Conn())
        await fixtures._insert({"kind": "goal", "name": "g"})
        await fixtures._insert(item)

    with pytest.raises(FixtureError, match="twice"):
        asyncio.run(go({"kind": "goal", "name": "g"}))
    with pytest.raises(FixtureError, match="unknown setup kind"):
        asyncio.run(go({"kind": "banana", "name": "b"}))


def test_news_article_id_is_the_md5_the_news_plugin_resolves():
    import hashlib

    async def go():
        fixtures = Fixtures(_Conn())
        await fixtures._insert(
            {
                "kind": "news_article",
                "name": "n",
                "fields": {"url": "https://exemplo.pt/ação"},
            }
        )
        return fixtures.bindings["n"]["id"]

    assert (
        asyncio.run(go())
        == hashlib.md5("https://exemplo.pt/ação".encode("utf-8")).hexdigest()
    )


def test_runner_fills_bindings_into_context_and_turns_only():
    scenario = {
        "id": "s",
        "prompt": "about {{wf.name}}",
        "expected_agent": "{{wf.name}}",
        "context": {"subject": [{"kind": "workflow", "id": "{{wf.id}}"}]},
        "turns": [{"prompt": "x {{wf.id}}"}],
    }
    out = runner._with_bindings(scenario, BINDINGS)
    assert out["context"]["subject"][0]["id"] == BINDINGS["wf"]["id"]
    assert out["turns"][0]["prompt"] == f"x {BINDINGS['wf']['id']}"
    assert out["prompt"] == "about Weekly report"
    assert out["expected_agent"] == "{{wf.name}}"


def test_describe_context_for_the_judge():
    text = describe_context(
        {
            "place": "doing",
            "origin": "chat_about",
            "subject": [{"kind": "workflow", "id": "w1", "label": "Weekly report"}],
            "focused_module": "Workflows",
        }
    )
    assert (
        text
        == 'place doing; started from "Chat about this"; subject: workflow "Weekly report"; focused module Workflows'
    )
    assert describe_context(None) == "none"


def test_the_judge_prompt_carries_the_screen_context():
    prompt = build_prompt(
        description="d",
        prompt="why did this fail?",
        response="r",
        expected_agent=None,
        agent_used=None,
        criteria=["names the run"],
        screen_context='place doing; subject: workflow_execution "Run"',
        today=date(2026, 10, 17),
    )
    assert (
        '## Screen context sent with the message\nplace doing; subject: workflow_execution "Run"'
        in prompt
    )
    plain = build_prompt(
        description="d",
        prompt="p",
        response="r",
        expected_agent=None,
        agent_used=None,
        criteria=[],
        today=date(2026, 10, 17),
    )
    assert "## Screen context sent with the message\nnone" in plain
