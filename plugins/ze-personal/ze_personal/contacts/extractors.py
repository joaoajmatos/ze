from __future__ import annotations

import email.utils
import re

from ze_agents.claims import ClaimKind
from ze_memory.graph.predicates import COLLABORATES_WITH, WORKS_ON
from ze_personal.contacts.types import (
    ContactProposal,
    ProjectProposal,
    RelationshipEdgeProposal,
    SOURCE_WEIGHTS,
    _SOURCE_TYPE_TO_PROVENANCE,
)
from ze_agents.types import ToolCall

# Matches a leading `[ProjectName]`-tagged subject/title — a common mailing-list
# / issue-tracker convention (e.g. "[repo] issue title") we treat as an explicit
# project mention without a second LLM pass (FR-003).
_BRACKET_TAG_RE = re.compile(r"\[([^\[\]]{2,60})\]")


def _extract_bracket_project(text: str) -> str | None:
    match = _BRACKET_TAG_RE.search(text or "")
    if not match:
        return None
    name = match.group(1).strip()
    return name or None


def extract_email_contacts(tool_calls: list[ToolCall]) -> list[ContactProposal]:
    """Return one proposal per unique sender seen in get_email results."""
    seen: set[str] = set()
    proposals: list[ContactProposal] = []

    for tc in tool_calls:
        if (
            tc.tool_name != "get_email"
            or not tc.success
            or not isinstance(tc.result, dict)
        ):
            continue
        from_header = tc.result.get("from", "")
        if not from_header:
            continue

        name, addr = email.utils.parseaddr(from_header)
        addr = addr.lower().strip()
        if not addr or addr in seen:
            continue
        seen.add(addr)

        if not name:
            name = addr.split("@")[0].replace(".", " ").title()

        proposals.append(
            ContactProposal(
                name=name,
                classification="unknown",
                relationship="email contact",
                contact_info={"email": addr},
                confidence=SOURCE_WEIGHTS["email"],
                confirmed=False,
                source_type="email",
                claim_kind=ClaimKind.IDENTITY,
                provenance=_SOURCE_TYPE_TO_PROVENANCE["email"],
            )
        )

    return proposals


def extract_calendar_contacts(tool_calls: list[ToolCall]) -> list[ContactProposal]:
    """Return one proposal per unique attendee across list_events / create_event results."""
    seen: set[str] = set()
    proposals: list[ContactProposal] = []

    for tc in tool_calls:
        if tc.tool_name not in ("list_events", "create_event") or not tc.success:
            continue

        events = tc.result if tc.tool_name == "list_events" else [tc.result]
        if not isinstance(events, list):
            continue

        for event in events:
            if not isinstance(event, dict):
                continue
            for attendee in event.get("attendees", []):
                if attendee.get("self"):
                    continue
                addr = (attendee.get("email") or "").lower().strip()
                if not addr or addr in seen:
                    continue
                seen.add(addr)

                name = (
                    attendee.get("displayName")
                    or addr.split("@")[0].replace(".", " ").title()
                )
                proposals.append(
                    ContactProposal(
                        name=name,
                        classification="unknown",
                        relationship="calendar contact",
                        contact_info={"email": addr},
                        confidence=SOURCE_WEIGHTS["calendar"],
                        confirmed=False,
                        source_type="calendar",
                        claim_kind=ClaimKind.IDENTITY,
                        provenance=_SOURCE_TYPE_TO_PROVENANCE["calendar"],
                    )
                )

    return proposals


def extract_email_social_edges(
    tool_calls: list[ToolCall],
) -> tuple[list[ProjectProposal], list[RelationshipEdgeProposal]]:
    """Detect `[ProjectName]`-tagged subjects on get_email results and emit a
    WORKS_ON edge from the sender to that project (research.md §4)."""
    projects: list[ProjectProposal] = []
    edges: list[RelationshipEdgeProposal] = []
    seen_projects: set[str] = set()

    for tc in tool_calls:
        if (
            tc.tool_name != "get_email"
            or not tc.success
            or not isinstance(tc.result, dict)
        ):
            continue
        subject = tc.result.get("subject", "")
        project_name = _extract_bracket_project(subject)
        if not project_name:
            continue

        from_header = tc.result.get("from", "")
        name, addr = email.utils.parseaddr(from_header)
        if not name and addr:
            name = addr.split("@")[0].replace(".", " ").title()
        if not name:
            continue

        if project_name.lower() not in seen_projects:
            seen_projects.add(project_name.lower())
            projects.append(
                ProjectProposal(
                    name=project_name,
                    confidence=SOURCE_WEIGHTS["email"],
                    source_type="email",
                    raw_context=subject[:500],
                )
            )
        edges.append(
            RelationshipEdgeProposal(
                predicate=WORKS_ON,
                person_name=name,
                target_name=project_name,
                confidence=SOURCE_WEIGHTS["email"],
                source_type="email",
                raw_context=subject[:500],
            )
        )

    return projects, edges


def extract_calendar_social_edges(
    tool_calls: list[ToolCall],
) -> tuple[list[ProjectProposal], list[RelationshipEdgeProposal]]:
    """Detect `[ProjectName]`-tagged event titles (WORKS_ON per attendee) and
    pairwise co-attendee collaboration (COLLABORATES_WITH) (research.md §4)."""
    projects: list[ProjectProposal] = []
    edges: list[RelationshipEdgeProposal] = []
    seen_projects: set[str] = set()
    seen_pairs: set[frozenset[str]] = set()

    for tc in tool_calls:
        if tc.tool_name not in ("list_events", "create_event") or not tc.success:
            continue

        events = tc.result if tc.tool_name == "list_events" else [tc.result]
        if not isinstance(events, list):
            continue

        for event in events:
            if not isinstance(event, dict):
                continue

            title = event.get("summary") or ""
            project_name = _extract_bracket_project(title)

            attendee_names: list[str] = []
            for attendee in event.get("attendees", []):
                if attendee.get("self"):
                    continue
                addr = (attendee.get("email") or "").lower().strip()
                name = attendee.get("displayName") or (
                    addr.split("@")[0].replace(".", " ").title() if addr else ""
                )
                if name:
                    attendee_names.append(name)

            if project_name:
                if project_name.lower() not in seen_projects:
                    seen_projects.add(project_name.lower())
                    projects.append(
                        ProjectProposal(
                            name=project_name,
                            confidence=SOURCE_WEIGHTS["calendar"],
                            source_type="calendar",
                            raw_context=title[:500],
                        )
                    )
                for attendee_name in attendee_names:
                    edges.append(
                        RelationshipEdgeProposal(
                            predicate=WORKS_ON,
                            person_name=attendee_name,
                            target_name=project_name,
                            confidence=SOURCE_WEIGHTS["calendar"],
                            source_type="calendar",
                            raw_context=title[:500],
                        )
                    )

            for i in range(len(attendee_names)):
                for j in range(i + 1, len(attendee_names)):
                    pair = frozenset((attendee_names[i], attendee_names[j]))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    edges.append(
                        RelationshipEdgeProposal(
                            predicate=COLLABORATES_WITH,
                            person_name=attendee_names[i],
                            target_name=attendee_names[j],
                            confidence=SOURCE_WEIGHTS["calendar"],
                            source_type="calendar",
                            raw_context=title[:500],
                        )
                    )

    return projects, edges
