from __future__ import annotations

import json
from typing import Any, Iterable


def normalize_fact_text(text: str) -> str:
    return " ".join(text.strip().casefold().split())


def fact_identity(predicate: str, value: str) -> tuple[str, str]:
    return normalize_fact_text(predicate), normalize_fact_text(value)


def remember_payload_ok(result: Any) -> bool:
    payload: dict[str, Any] | None
    if isinstance(result, dict):
        payload = result
    elif isinstance(result, str):
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return False
        payload = parsed if isinstance(parsed, dict) else None
    else:
        payload = None
    return payload is not None and payload.get("ok") is True


def identities_from_remember_calls(tool_calls: Iterable[Any]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for call in tool_calls:
        if getattr(call, "tool_name", None) != "remember_fact":
            continue
        if not remember_payload_ok(getattr(call, "result", None)):
            continue
        args = getattr(call, "args", None) or {}
        pred = str(args.get("predicate") or "")
        value = str(args.get("value") or "")
        if not pred.strip() or not value.strip():
            continue
        out.add(fact_identity(pred, value))
    return out
