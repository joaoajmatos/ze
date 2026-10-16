import asyncio

from ze_agents.tool import ToolAccess, tool
from ze_sdk import ToolReversibility
from ze_google.auth import GoogleCredentials
from ze_sdk.contribution import ActionLifecycle, ActionOutcome
from ze_calendar.action_records import emit_calendar_mutation


def _calendar_write_view(args: dict) -> dict:
    parties = []
    summary = args.get("summary") or ""
    location = args.get("location") or ""
    if summary:
        parties.append(summary)
    return {
        "kind": "calendar_mutation",
        "channel": "calendar",
        "parties": parties,
        "when": args.get("start"),
        "summary": summary or args.get("event_id") or location or "calendar write",
        "sets_time": bool(args.get("start") or args.get("end")),
    }


@tool(access=ToolAccess.READ, description="List upcoming Google Calendar events.")
async def list_events(
    credentials: GoogleCredentials,
    calendar_id: str = "primary",
    max_results: int = 10,
    query: str = "",
) -> list:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    service = credentials.calendar()
    result = await asyncio.to_thread(
        lambda: (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
                **({"q": query} if query else {}),
            )
            .execute()
        )
    )
    return result.get("items", [])


@tool(
    access=ToolAccess.WRITE,
    description="Create a new Google Calendar event.",
    constraint_gate=True,
    constraint_describe=_calendar_write_view,
    reversibility=ToolReversibility.IRREVERSIBLE,
    effect_phrase="created a calendar event",
)
async def create_event(
    credentials: GoogleCredentials,
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    calendar_id: str = "primary",
) -> dict:
    body: dict = {
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location

    service = credentials.calendar()
    try:
        result = await asyncio.to_thread(
            lambda: service.events().insert(calendarId=calendar_id, body=body).execute()
        )
    except Exception as exc:
        log_id = ""
        await emit_calendar_mutation(
            action_kind="create",
            event_id=log_id,
            lifecycle=ActionLifecycle.FAILED,
            outcome=ActionOutcome.FAILURE,
            failure_code=type(exc).__name__,
        )
        raise
    event_id = result.get("id") or ""
    await emit_calendar_mutation(
        action_kind="create",
        event_id=event_id,
        lifecycle=ActionLifecycle.SUCCEEDED,
        outcome=ActionOutcome.SUCCESS,
    )
    return {"id": event_id, "htmlLink": result.get("htmlLink")}


async def _event_label(args: dict) -> str | None:
    """The event's title and start, read from the calendar, for a confirmation."""
    service = args["credentials"].calendar()
    event = await asyncio.to_thread(
        lambda: (
            service.events()
            .get(
                calendarId=args.get("calendar_id") or "primary",
                eventId=args["event_id"],
            )
            .execute()
        )
    )
    start = event.get("start") or {}
    when = start.get("dateTime") or start.get("date") or ""
    return f'"{event.get("summary") or "untitled event"}" {when}'.strip()


async def _event_change_label(args: dict) -> str | None:
    label = await _event_label(args)
    changes = ", ".join(
        f"{key}: {args[key]}"
        for key in ("summary", "start", "end", "description")
        if args.get(key) is not None
    )
    return f"{label} → {changes}" if changes else label


@tool(
    access=ToolAccess.WRITE,
    description="Update an existing Google Calendar event.",
    summarize=_event_change_label,
    constraint_gate=True,
    constraint_describe=_calendar_write_view,
    reversibility=ToolReversibility.IRREVERSIBLE,
    effect_phrase="changed a calendar event",
)
async def update_event(
    credentials: GoogleCredentials,
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    description: str | None = None,
    calendar_id: str = "primary",
) -> dict:
    service = credentials.calendar()
    existing = await asyncio.to_thread(
        lambda: service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    )
    if summary is not None:
        existing["summary"] = summary
    if start is not None:
        existing["start"] = {"dateTime": start}
    if end is not None:
        existing["end"] = {"dateTime": end}
    if description is not None:
        existing["description"] = description

    try:
        result = await asyncio.to_thread(
            lambda: (
                service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=existing)
                .execute()
            )
        )
    except Exception as exc:
        await emit_calendar_mutation(
            action_kind="update",
            event_id=event_id,
            lifecycle=ActionLifecycle.FAILED,
            outcome=ActionOutcome.FAILURE,
            failure_code=type(exc).__name__,
        )
        raise
    await emit_calendar_mutation(
        action_kind="update",
        event_id=result.get("id") or event_id,
        lifecycle=ActionLifecycle.SUCCEEDED,
        outcome=ActionOutcome.SUCCESS,
    )
    return {"id": result.get("id"), "htmlLink": result.get("htmlLink")}


@tool(
    access=ToolAccess.WRITE,
    description="Delete a Google Calendar event.",
    summarize=_event_label,
    constraint_gate=True,
    constraint_describe=_calendar_write_view,
    reversibility=ToolReversibility.IRREVERSIBLE,
    effect_phrase="deleted a calendar event",
)
async def delete_event(
    credentials: GoogleCredentials,
    event_id: str,
    calendar_id: str = "primary",
) -> None:
    service = credentials.calendar()
    try:
        await asyncio.to_thread(
            lambda: (
                service.events()
                .delete(calendarId=calendar_id, eventId=event_id)
                .execute()
            )
        )
    except Exception as exc:
        await emit_calendar_mutation(
            action_kind="delete",
            event_id=event_id,
            lifecycle=ActionLifecycle.FAILED,
            outcome=ActionOutcome.FAILURE,
            failure_code=type(exc).__name__,
        )
        raise
    await emit_calendar_mutation(
        action_kind="delete",
        event_id=event_id,
        lifecycle=ActionLifecycle.SUCCEEDED,
        outcome=ActionOutcome.SUCCESS,
    )
