from __future__ import annotations

from typing import Any

from ze_agents.errors import RetryRewindError

# The node that appends the exchange to the checkpointed `messages` channel.
_WRITER_NODE = "write_memory"


def _ends_in_exchange(messages: list[dict]) -> bool:
    return (
        len(messages) >= 2
        and messages[-2].get("role") == "user"
        and messages[-1].get("role") == "assistant"
    )


async def history_rewindable(graph: Any, config: dict) -> bool:
    """True when the checkpointed history ends in a user/assistant pair.

    Checked before a rollback so nothing is undone for a retry that cannot regenerate.
    """
    snapshot = await graph.aget_state(config)
    values = getattr(snapshot, "values", None) or {}
    return _ends_in_exchange(list(values.get("messages") or []))


async def rewind_last_exchange(graph: Any, config: dict) -> list[dict]:
    """Drop the final user/assistant pair from the thread's checkpointed `messages`.

    Returns the original list so the caller can `restore_messages` if the retry
    fails. Uses a state update on the live thread rather than forking an older
    checkpoint, so the thread's latest checkpoint is always a coherent state.
    """
    snapshot = await graph.aget_state(config)
    values = getattr(snapshot, "values", None) or {}
    original = list(values.get("messages") or [])
    if not _ends_in_exchange(original):
        raise RetryRewindError("thread history does not end with a user/assistant pair")
    await graph.aupdate_state(config, {"messages": original[:-2]}, as_node=_WRITER_NODE)
    return original


async def restore_messages(graph: Any, config: dict, messages: list[dict]) -> None:
    await graph.aupdate_state(config, {"messages": messages}, as_node=_WRITER_NODE)
