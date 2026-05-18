import asyncio
from dataclasses import dataclass, field


@dataclass
class _SessionEntry:
    active: bool = False
    awaiting_edit_reply: bool = False
    pending_config: dict | None = None
    confirm_task: asyncio.Task | None = None


class ActiveSessionStore:
    """Tracks in-flight graph invocations and ForceReply state per chat_id.

    State is in-memory only. On server restart, a new message from the user
    will be processed normally — the graph state survives via Postgres.
    """

    def __init__(self) -> None:
        self._sessions: dict[int, _SessionEntry] = {}

    def _get(self, chat_id: int) -> _SessionEntry:
        if chat_id not in self._sessions:
            self._sessions[chat_id] = _SessionEntry()
        return self._sessions[chat_id]

    def is_active(self, chat_id: int) -> bool:
        return self._get(chat_id).active

    def mark_active(self, chat_id: int) -> None:
        self._get(chat_id).active = True

    def clear_active(self, chat_id: int) -> None:
        self._get(chat_id).active = False

    def set_pending_confirmation(
        self,
        chat_id: int,
        config: dict,
        timeout_task: asyncio.Task,
    ) -> None:
        entry = self._get(chat_id)
        entry.pending_config = config
        entry.confirm_task = timeout_task

    def get_pending_config(self, chat_id: int) -> dict | None:
        return self._get(chat_id).pending_config

    def cancel_confirm_task(self, chat_id: int) -> None:
        entry = self._get(chat_id)
        if entry.confirm_task:
            entry.confirm_task.cancel()
            entry.confirm_task = None
        entry.pending_config = None

    def set_awaiting_edit(self, chat_id: int) -> None:
        self._get(chat_id).awaiting_edit_reply = True

    def is_awaiting_edit(self, chat_id: int) -> bool:
        return self._get(chat_id).awaiting_edit_reply

    def clear_awaiting_edit(self, chat_id: int) -> None:
        self._get(chat_id).awaiting_edit_reply = False

    def clear_all(self, chat_id: int) -> None:
        self.cancel_confirm_task(chat_id)
        entry = self._get(chat_id)
        entry.active = False
        entry.awaiting_edit_reply = False
