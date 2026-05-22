from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator
from uuid import UUID

from ze.agents.base import BaseAgent
from ze.agents.registry import register
from ze.agents.types import AgentContext, AgentResult
from ze.openrouter.client import OpenRouterClient
from ze.proactive.notifier import ProactiveNotifier
from ze.reminders.store import ReminderStore, fire_reminder
from ze.settings import Settings
from ze.workflow.scheduler import WorkflowScheduler

_PARSE_SYSTEM = """\
You extract reminder details from user requests.

Current UTC time: {now}
User timezone: {timezone}

Return a JSON object with exactly these keys:
{{
  "action": "set" | "list" | "cancel",
  "label": "<what to remind about — concise imperative, e.g. 'Take medication'>",
  "fire_at": "<ISO 8601 UTC datetime string, or null for list/cancel>",
  "cancel_hint": "<keywords from the reminder to cancel, or null>"
}}

For relative times ("in 2 hours", "tomorrow at 9am"), compute the absolute UTC datetime
using the current time and user timezone above.
If no label is specified for a set action, use "Reminder".
Return ONLY the JSON object — no explanation.\
"""


@register
class RemindersAgent(BaseAgent):
    name = "reminders"
    tools: list[str] = []

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        reminder_store: ReminderStore,
        workflow_scheduler: WorkflowScheduler,
        notifier: ProactiveNotifier,
        settings: Settings,
    ) -> None:
        super().__init__(settings)
        self._client = openrouter_client
        self._store = reminder_store
        self._scheduler = workflow_scheduler
        self._notifier = notifier

    async def run(self, ctx: AgentContext) -> AgentResult:
        await self.emit(ctx, "reminders.thinking")

        now = datetime.now(timezone.utc)
        raw = await self._client.complete(
            messages=[{"role": "user", "content": ctx.prompt}],
            model=self._model(ctx),
            system=_PARSE_SYSTEM.format(
                now=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                timezone=self._settings.timezone,
            ),
            max_tokens=200,
        )

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return AgentResult(
                agent=self.name,
                response="I couldn't understand that reminder request. Try: 'remind me in 2 hours to call João'.",
            )

        action = parsed.get("action", "set")
        match action:
            case "set":
                response = await self._handle_set(parsed, now)
            case "list":
                response = await self._handle_list()
            case "cancel":
                response = await self._handle_cancel(parsed)
            case _:
                response = "Unknown reminder action."

        self._log.info("reminders_agent_complete", session_id=ctx.session_id, action=action)
        return AgentResult(agent=self.name, response=response)

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        result = await self.run(ctx)
        yield result.response

    # ── Handlers ─────────────────────────────────────────────────────────────

    async def _handle_set(self, parsed: dict, now: datetime) -> str:
        label = (parsed.get("label") or "Reminder").strip()
        fire_at_str = parsed.get("fire_at")

        if not fire_at_str:
            return "I need a time to set the reminder. Try: 'remind me in 2 hours'."

        try:
            fire_at = datetime.fromisoformat(fire_at_str).astimezone(timezone.utc)
        except (ValueError, TypeError):
            return "I couldn't parse that time. Try something like 'remind me in 2 hours'."

        if fire_at <= now:
            return "That time is already in the past. Please give me a future time."

        rid = await self._store.create(label=label, fire_at=fire_at)
        self._scheduler.schedule_at(
            fn=lambda r=rid: fire_reminder(self._store, self._notifier, r),
            dt=fire_at,
            job_id=f"user_reminder:{rid}",
        )

        human = _human_delta(fire_at - now)
        time_str = fire_at.strftime("%a %d %b at %H:%M UTC")
        return f"⏰ Reminder set: {label}\nI'll remind you {human} ({time_str})"

    async def _handle_list(self) -> str:
        pending = await self._store.list_pending()
        if not pending:
            return "You have no pending reminders."
        lines = [f"⏰ Pending reminders ({len(pending)}):"]
        for i, r in enumerate(pending, 1):
            lines.append(f"  {i}. {r.label} — {r.fire_at.strftime('%a %d %b at %H:%M UTC')}")
        return "\n".join(lines)

    async def _handle_cancel(self, parsed: dict) -> str:
        hint = (parsed.get("cancel_hint") or "").strip().lower()
        pending = await self._store.list_pending()

        if not pending:
            return "You have no pending reminders to cancel."

        matches = [r for r in pending if hint and hint in r.label.lower()]
        if not matches:
            lines = ["I couldn't find a reminder matching that. Your pending reminders:\n"]
            for i, r in enumerate(pending, 1):
                lines.append(f"  {i}. {r.label} — {r.fire_at.strftime('%a %d %b at %H:%M UTC')}")
            lines.append("\nTell me which one you'd like to cancel.")
            return "\n".join(lines)

        target = matches[0]
        self._scheduler.remove_job_if_exists(f"user_reminder:{target.id}")
        await self._store.delete(target.id)
        return f"✅ Reminder cancelled: {target.label}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _human_delta(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    days = total // 86400
    hours = (total % 86400) // 3600
    minutes = (total % 3600) // 60

    parts: list[str] = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes and not days:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    if not parts:
        parts = ["less than a minute"]
    return "in " + " ".join(parts)
