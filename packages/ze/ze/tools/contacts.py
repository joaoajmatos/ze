import json
import time
from uuid import UUID

import structlog

from ze_core.orchestration.tool import ToolAccess, tool
from ze.agents.types import ToolCall
from ze_core.channels.types import ChannelHandle, ChannelType
from ze.contacts.channel_store import ContactChannelStore
from ze_core.openrouter.client import OpenRouterClient

log = structlog.get_logger(__name__)

_SYSTEM = (
    "You identify named people the user explicitly introduces in a conversation. "
    "Only include people the user names AND provides identifying context for "
    "(job title, company, relationship, etc.). "
    "Do not include vague references like 'a colleague', 'someone I met', or 'a friend'. "
    "Do not include well-known public figures unless the user has a direct personal connection. "
    "Return a JSON array — no markdown, no explanation, just the array. "
    'Each item: {"name": "full name", '
    '"classification": "personal"|"professional"|"unknown", '
    '"relationship": "how they relate to the user (free text)", '
    '"contact_info": {}, '
    '"confidence": 0.0-1.0}. '
    "Use confidence 0.8+ only when both name and context are clearly stated. "
    "Return [] if no named individuals are explicitly introduced."
)

_MIN_CONFIDENCE = 0.7


@tool(access=ToolAccess.READ, description="Extract named people explicitly introduced in a conversation turn.")
async def extract_contacts(
    prompt: str,
    response: str,
    client: OpenRouterClient,
    model: str,
) -> ToolCall:
    args = {"prompt": prompt[:200], "response": response[:200]}
    start = time.monotonic()
    try:
        raw = await client.complete(
            messages=[{
                "role": "user",
                "content": f"User said: {prompt}\n\nAssistant replied: {response[:1000]}",
            }],
            model=model,
            system=_SYSTEM,
            max_tokens=400,
        )
        contacts = _parse(raw)
        duration_ms = int((time.monotonic() - start) * 1000)
        return ToolCall(
            tool_name="extract_contacts",
            args=args,
            result=contacts,
            duration_ms=duration_ms,
            success=True,
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.warning("extract_contacts_failed", error=str(exc))
        return ToolCall(
            tool_name="extract_contacts",
            args=args,
            result=[],
            duration_ms=duration_ms,
            success=False,
            error=str(exc),
        )


def _parse(raw: str) -> list[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            return []
        return [
            {
                "name": str(c["name"]).strip(),
                "classification": _safe_classification(c.get("classification")),
                "relationship": str(c.get("relationship", "")).strip(),
                "contact_info": dict(c.get("contact_info") or {}),
                "confidence": float(c.get("confidence", 0.8)),
            }
            for c in parsed
            if isinstance(c, dict) and c.get("name", "").strip()
            and float(c.get("confidence", 0.0)) >= _MIN_CONFIDENCE
        ]
    except (json.JSONDecodeError, KeyError, ValueError):
        return []


def _safe_classification(value: object) -> str:
    if value in ("personal", "professional"):
        return str(value)
    return "unknown"


@tool(access=ToolAccess.READ, description="Get all known communication channel handles (email, LinkedIn, etc.) for a contact.")
async def get_contact_channels(
    contact_id: str,
    contact_channel_store: ContactChannelStore,
) -> ToolCall:
    args = {"contact_id": contact_id}
    start = time.monotonic()
    try:
        handles = await contact_channel_store.get_handles(UUID(contact_id))
        result = [
            {
                "channel_type": h.channel_type.value,
                "handle": h.handle,
                "preferred": h.preferred,
                "verified": h.verified,
            }
            for h in handles
        ]
        return ToolCall(
            tool_name="get_contact_channels",
            args=args,
            result=result,
            duration_ms=int((time.monotonic() - start) * 1000),
            success=True,
        )
    except Exception as exc:
        log.warning("get_contact_channels_failed", error=str(exc))
        return ToolCall(
            tool_name="get_contact_channels",
            args=args,
            result=[],
            duration_ms=int((time.monotonic() - start) * 1000),
            success=False,
            error=str(exc),
        )


@tool(access=ToolAccess.WRITE, description="Add or update a communication channel handle for a contact.")
async def set_contact_channel(
    contact_id: str,
    channel_type: str,
    handle: str,
    contact_channel_store: ContactChannelStore,
    preferred: bool = False,
) -> ToolCall:
    args = {"contact_id": contact_id, "channel_type": channel_type, "handle": handle}
    start = time.monotonic()
    try:
        ch = ChannelHandle(
            channel_type=ChannelType(channel_type),
            handle=handle,
            preferred=preferred,
        )
        await contact_channel_store.upsert(UUID(contact_id), ch)
        return ToolCall(
            tool_name="set_contact_channel",
            args=args,
            result={"status": "ok", "channel_type": channel_type, "handle": handle},
            duration_ms=int((time.monotonic() - start) * 1000),
            success=True,
        )
    except Exception as exc:
        log.warning("set_contact_channel_failed", error=str(exc))
        return ToolCall(
            tool_name="set_contact_channel",
            args=args,
            result=None,
            duration_ms=int((time.monotonic() - start) * 1000),
            success=False,
            error=str(exc),
        )
