import time
from uuid import UUID

import asyncpg

from ze.agents.tool import ToolAccess, tool
from ze.agents.types import ToolCall
from ze.contacts.store import PersonStore
from ze.contacts.types import Person, PersonSource
from ze.logging import get_logger
from ze.openrouter.client import OpenRouterClient

log = get_logger(__name__)

_DRAFT_SYSTEM = (
    "You write concise, personalised outreach messages. "
    "Write only the message body — no subject line, no greeting, no sign-off. "
    "Tailor the message to the person's role and company based on the context provided."
)


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Add a prospective contact found during research. "
        "Sets confirmed=False and source_type='research'. "
        "Call once per person found — deduplication is automatic."
    ),
)
async def add_prospect(
    name: str,
    company: str | None,
    role: str | None,
    relationship: str,
    contact_info: dict,
    source_url: str,
    enrichment_notes: str,
    campaign_id: str,
    person_store: PersonStore,
    pool: asyncpg.Pool,
) -> ToolCall:
    args = {
        "name": name,
        "company": company,
        "role": role,
        "relationship": relationship,
        "source_url": source_url,
        "enrichment_notes": enrichment_notes,
        "campaign_id": campaign_id,
    }
    start = time.monotonic()
    try:
        existing = await person_store.get_by_name(name)
        if existing:
            person = existing[0]
            await person_store.add_source(
                person.id,
                PersonSource(
                    person_id=person.id,
                    source_type="research",
                    weight=0.2,
                    raw_context=f"source: {source_url}\n{enrichment_notes}",
                ),
            )
        else:
            rel = relationship
            if company and role:
                rel = f"{role} at {company} — {relationship}"
            elif company:
                rel = f"{company} — {relationship}"
            elif role:
                rel = f"{role} — {relationship}"

            person = await person_store.upsert(
                Person(
                    name=name,
                    classification="professional",
                    classification_confidence=0.6,
                    relationship_to_user=rel,
                    contact_info=contact_info or {},
                    notes=enrichment_notes,
                    confirmed=False,
                    confidence=0.2,
                )
            )
            await person_store.add_source(
                person.id,
                PersonSource(
                    person_id=person.id,
                    source_type="research",
                    weight=0.2,
                    raw_context=f"source: {source_url}\n{enrichment_notes}",
                ),
            )

        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                INSERT INTO prospect_outreach (campaign_id, contact_id, channel, status)
                VALUES ($1, $2, 'email', 'pending')
                ON CONFLICT (campaign_id, contact_id) DO NOTHING
                """,
                UUID(campaign_id),
                person.id,
            )
            if result == "INSERT 0 1":
                await conn.execute(
                    "UPDATE prospect_campaigns SET found_count = found_count + 1 WHERE id = $1",
                    UUID(campaign_id),
                )

        duration_ms = int((time.monotonic() - start) * 1000)
        return ToolCall(
            tool_name="add_prospect",
            args=args,
            result=f"Added {name} (id={person.id})",
            duration_ms=duration_ms,
            success=True,
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.warning("add_prospect_failed", name=name, error=str(exc))
        return ToolCall(
            tool_name="add_prospect",
            args=args,
            result=None,
            duration_ms=duration_ms,
            success=False,
            error=str(exc),
        )


@tool(
    access=ToolAccess.WRITE,
    description="Draft a personalised outreach message for a prospect and save it.",
)
async def draft_outreach(
    name: str,
    context: str,
    campaign_brief: str,
    channel: str,
    campaign_id: str,
    client: OpenRouterClient,
    model: str,
    person_store: PersonStore,
    pool: asyncpg.Pool,
) -> ToolCall:
    args = {
        "name": name,
        "context": context,
        "campaign_brief": campaign_brief,
        "channel": channel,
    }
    start = time.monotonic()
    try:
        matches = await person_store.get_by_name(name)
        if not matches:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolCall(
                tool_name="draft_outreach",
                args=args,
                result=f"No contact found for {name!r}",
                duration_ms=duration_ms,
                success=False,
                error=f"contact not found: {name!r}",
            )

        person = matches[0]

        prompt = (
            f"Campaign goal: {campaign_brief}\n"
            f"Prospect: {name}\n"
            f"Context: {context}\n"
            f"Channel: {channel}\n\n"
            "Write a personalised outreach message (body only, no greeting or sign-off)."
        )
        draft = await client.complete(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            system=_DRAFT_SYSTEM,
            max_tokens=400,
        )

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE prospect_outreach
                SET draft = $3
                WHERE campaign_id = $1 AND contact_id = $2
                """,
                UUID(campaign_id),
                person.id,
                draft,
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        return ToolCall(
            tool_name="draft_outreach",
            args=args,
            result=draft,
            duration_ms=duration_ms,
            success=True,
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.warning("draft_outreach_failed", name=name, error=str(exc))
        return ToolCall(
            tool_name="draft_outreach",
            args=args,
            result=None,
            duration_ms=duration_ms,
            success=False,
            error=str(exc),
        )


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Record that the user sent a message to a prospect or received a reply. "
        "Call when the user explicitly mentions contacting someone or getting a response."
    ),
)
async def log_outreach_event(
    contact_name: str,
    event_type: str,
    channel: str,
    notes: str,
    pool: asyncpg.Pool,
    person_store: PersonStore,
) -> ToolCall:
    args = {
        "contact_name": contact_name,
        "event_type": event_type,
        "channel": channel,
        "notes": notes,
    }
    start = time.monotonic()
    try:
        matches = await person_store.get_by_name(contact_name)

        if not matches:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolCall(
                tool_name="log_outreach_event",
                args=args,
                result=f"No contact found for {contact_name!r} — no outreach event logged",
                duration_ms=duration_ms,
                success=False,
                error=f"contact not found: {contact_name!r}",
            )

        if len(matches) > 1:
            names_str = " and ".join(m.name for m in matches[:3])
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolCall(
                tool_name="log_outreach_event",
                args=args,
                result=f"Ambiguous: found {names_str} — please clarify",
                duration_ms=duration_ms,
                success=False,
                error="ambiguous contact name",
            )

        person = matches[0]
        ts_col = _ts_column(event_type)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM prospect_outreach
                WHERE contact_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                person.id,
            )

            if row:
                ts_clause = f", {ts_col} = NOW()" if ts_col else ""
                await conn.execute(
                    f"UPDATE prospect_outreach SET status = $2, notes = $3{ts_clause} WHERE id = $1",
                    row["id"],
                    event_type,
                    notes,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO prospect_outreach (contact_id, channel, status, notes)
                    VALUES ($1, $2, $3, $4)
                    """,
                    person.id,
                    channel,
                    event_type,
                    notes,
                )

        duration_ms = int((time.monotonic() - start) * 1000)
        return ToolCall(
            tool_name="log_outreach_event",
            args=args,
            result=f"Logged {event_type} for {person.name}",
            duration_ms=duration_ms,
            success=True,
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.warning("log_outreach_event_failed", contact_name=contact_name, error=str(exc))
        return ToolCall(
            tool_name="log_outreach_event",
            args=args,
            result=None,
            duration_ms=duration_ms,
            success=False,
            error=str(exc),
        )


def _ts_column(event_type: str) -> str | None:
    return {"sent": "sent_at", "replied": "replied_at"}.get(event_type)
