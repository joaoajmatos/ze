"""A small compiled graph around the real execution and confirmation nodes (Phase 181).

Only the nodes around the confirmation path are stubbed; `preflight`,
`execute_tool`, `await_write_confirmation` and `await_budget_confirmation` are real.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from langgraph.checkpoint.memory import MemorySaver

from ze_agents.base_agent import BaseAgent
from ze_agents.registry import agent, register_instance
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, tool
from ze_agents.types import AgentContext, AgentResult
from ze_core.orchestration.edges import after_embed_route
from ze_core.orchestration.graph import graph_builder
from ze_core.routing.types import RoutingEnvelope, SubTask

calls: list[tuple[str, dict]] = []


def tc(id_: str, name: str, **args):
    return {"id": id_, "name": name, "arguments": args}


def scripted_client(*responses):
    queue = list(responses)
    client = MagicMock()

    async def _complete(**kw):
        return queue.pop(0)

    client.complete_with_tools = AsyncMock(side_effect=_complete)
    client.complete = AsyncMock(return_value="fallback")
    return client


def register_tools() -> None:
    async def list_events() -> str:
        calls.append(("list_events", {}))
        return "3pm dentist"

    tool(access=ToolAccess.READ, description="list")(list_events)

    async def delete_event(event_id: str = "") -> str:
        calls.append(("delete_event", {"event_id": event_id}))
        return f"deleted {event_id}"

    tool(
        access=ToolAccess.WRITE,
        description="delete",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="deleted a calendar event",
    )(delete_event)

    async def send_email(to: str = "", body: str = "") -> str:
        calls.append(("send_email", {"to": to, "body": body}))
        return "sent"

    tool(
        access=ToolAccess.WRITE,
        description="send",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="sent an email",
        editable_field="body",
    )(send_email)

    async def ingest_text(text: str = "") -> str:
        calls.append(("ingest_text", {"text": text}))
        return "saved"

    tool(
        access=ToolAccess.WRITE,
        description="ingest",
        reversibility=ToolReversibility.IRREVERSIBLE,
        asks_first=False,
        no_ask_reason="saves content the user asked to save",
        effect_phrase="ingested text",
    )(ingest_text)

    async def archive_note(note_id: str = "") -> str:
        calls.append(("archive_note", {"note_id": note_id}))
        return "archived"

    tool(
        access=ToolAccess.WRITE,
        description="note",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="delete_event",
        undo_note="n",
        effect_phrase="archived a note",
    )(archive_note)


def register_agent(name: str, client, tools: list[str], *, enabled: bool = True):
    async def _run(self, ctx: AgentContext) -> AgentResult:
        text, tcs = await self.agentic_loop(
            ctx, client, list(ctx.messages), system="s", tool_names=list(tools)
        )
        return AgentResult(agent=self.name, response=text, tool_calls=tcs)

    cls = type(
        f"_Agent_{name}",
        (BaseAgent,),
        {
            "name": name,
            "description": name,
            "tools": list(tools),
            "run": _run,
            "enabled": enabled,
        },
    )
    agent(cls)
    register_instance(name, cls())


def compiled_graph(
    subtasks: list[SubTask],
    *,
    compound: bool = False,
    saver=None,
    overrides: dict | None = None,
):
    envelope = RoutingEnvelope(
        primary_agent=subtasks[0].agent,
        confidence=1.0,
        score_gap=1.0,
        routing_method="forced",
        is_compound=compound,
        subtasks=subtasks,
        requires_synthesis=compound,
    )

    async def noop(state, config=None):
        return {}

    async def embed_route(state):
        return {"envelope": envelope}

    async def fetch_context(state):
        return {
            "agent_context": AgentContext(
                session_id=state["session_id"],
                prompt=state["prompt"],
                intent="read",
                messages=[{"role": "user", "content": state["prompt"]}],
            )
        }

    async def synthesize(state, config=None):
        parts = [f"{r.agent}: {r.response}" for r in state.get("subtask_results") or []]
        return {"final_response": " | ".join(parts)}

    node_overrides = {
        "preprocess": noop,
        "embed_route": embed_route,
        "fetch_context": fetch_context,
        "match_skills": noop,
        "correlate": noop,
        "surface_loops": noop,
        "synthesize": synthesize,
        "write_memory": noop,
    }
    node_overrides.update(overrides or {})
    builder = graph_builder(node_overrides=node_overrides)
    builder.add_conditional_edges(
        "embed_route",
        after_embed_route,
        {"decompose": "decompose", "fetch_context": "fetch_context"},
    )
    builder.add_edge("decompose", "fetch_context")
    return builder.compile(checkpointer=saver or MemorySaver())


def graph_input(prompt: str, thread: str = "t1") -> dict:
    from ze_agents.interface.types import RawInput
    from ze_core.conversation.turn import make_graph_input

    return make_graph_input(RawInput(text=prompt), thread)


def thread_config(thread: str = "t1", **extra) -> dict:
    return {"configurable": {"thread_id": thread, **extra}}
