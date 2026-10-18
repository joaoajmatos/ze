from __future__ import annotations

_NAMES = {
    "col": "card",
    "row": "card",
    "text": "card",
    "badge": "card",
    "steps": "step list",
    "connections": "connection map",
    "headline": "headline",
    "claim_card": "card",
    "claim_timeline": "timeline",
    "entity_facet": "fact list",
    "stat_row": "stat row",
    "claim_list": "claim list",
    "sparkline": "sparkline",
    "card": "card",
}


def describe_components(components: list[dict] | None) -> str:
    """A short sentence naming what a reply showed, for history and push bodies."""
    kinds: list[str] = []
    for component in components or []:
        raw = component.get("type") if isinstance(component, dict) else None
        kind = _NAMES.get(raw, raw or "card")
        if kind not in kinds:
            kinds.append(kind)
    if not kinds:
        return ""
    return "Showed " + _join(kinds) + "."


def _join(kinds: list[str]) -> str:
    named = [f"a {k}" for k in kinds]
    if len(named) == 1:
        return named[0]
    return ", ".join(named[:-1]) + " and " + named[-1]
