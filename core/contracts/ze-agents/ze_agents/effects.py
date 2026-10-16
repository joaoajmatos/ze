"""Imperative effect phrases and the code-guaranteed "Okay, I didn't ..." line (Phase 181).

A tool declares its effect in the past tense ("deleted a calendar event"). The
confirmation card and the denial line both need the imperative ("delete a calendar
event"), so one helper converts it.
"""

from __future__ import annotations

from typing import Any

DENIED_OUTCOMES = frozenset({"denied", "timed_out", "superseded"})

# Past tense -> base form. Every verb used by a registered `effect_phrase` is listed;
# an author who adds a new verb adds it here (a test fails otherwise).
_PAST_TO_BASE: dict[str, str] = {
    "abandoned": "abandon",
    "added": "add",
    "archived": "archive",
    "cancelled": "cancel",
    "changed": "change",
    "closed": "close",
    "confirmed": "confirm",
    "created": "create",
    "deleted": "delete",
    "did": "do",
    "disabled": "disable",
    "dismissed": "dismiss",
    "drafted": "draft",
    "dropped": "drop",
    "edited": "edit",
    "enabled": "enable",
    "forgot": "forget",
    "ingested": "ingest",
    "logged": "log",
    "paused": "pause",
    "ran": "run",
    "reset": "reset",
    "resumed": "resume",
    "saved": "save",
    "sent": "send",
    "set": "set",
    "started": "start",
    "steered": "steer",
    "wrote": "write",
}


def _regular_base(word: str) -> str:
    if word.endswith("ied") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ed") and len(word) > 3:
        stem = word[:-2]
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiouls":
            return stem[:-1]
        if stem.endswith(("at", "iv", "uc", "ut", "iz", "ak", "os", "am", "ov", "ur")):
            return stem + "e"
        return stem
    return word


def effect_imperative(phrase: str) -> str:
    """Convert a past-tense effect phrase to the imperative: first word only."""
    head, sep, rest = phrase.strip().partition(" ")
    base = _PAST_TO_BASE.get(head.lower())
    if base is None:
        base = _regular_base(head.lower())
    if head[:1].isupper():
        base = base.capitalize()
    return f"{base}{sep}{rest}"


def ensure_declined_lines(reply: str, outcomes: list[dict[str, Any]]) -> str:
    """Append "Okay, I didn't <effect>." for each declined item the reply omits.

    `outcomes` are the trace rows (`write_outcomes`); only items the user denied,
    that timed out or that a new turn superseded count. Code, not the model,
    guarantees the user hears that nothing happened.
    """
    lowered = (reply or "").lower()
    lines: list[str] = []
    for row in outcomes:
        if row.get("outcome") not in DENIED_OUTCOMES:
            continue
        effect = str(row.get("effect") or "").strip()
        if not effect or effect.lower() in lowered:
            continue
        line = f"Okay, I didn't {effect}."
        if line.lower() not in (seen.lower() for seen in lines):
            lines.append(line)
    if not lines:
        return reply
    return "\n\n".join(part for part in [(reply or "").rstrip(), *lines] if part)
