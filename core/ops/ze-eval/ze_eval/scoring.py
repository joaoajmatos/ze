"""
Objective scoring functions for eval scenarios.

These are deterministic checks — no LLM calls. Each returns True/False/None
where None means the scenario did not declare that expectation.
"""

from __future__ import annotations

from ze_eval.types import VerifyResult


def routing_correct(scenario: dict, agent_used: str | None) -> bool | None:
    expected = scenario.get("expected_agent")
    if not expected or not agent_used:
        return None
    return agent_used == expected


_DID_NOT_RUN = frozenset(
    {"parked", "denied", "refused", "expired", "refused_over_cap", "duplicate"}
)


def tools_correct(scenario: dict, ze_result: dict) -> bool | None:
    """
    Check that every tool listed in expected_tools was called and succeeded.

    Each entry may be a bare string (name only) or a dict with 'name' and
    optional 'args', 'allow_parked', 'gate', 'count' and 'turn'. Returns None when the
    scenario declares no expected_tools.

    A call that waits for the user's approval (``gate`` "parked") or that the
    user denied, let expire or hit the confirmation cap did not run, so it never
    counts by default; ``allow_parked: true`` accepts a parked call as well. A
    ``gate`` entry (a gate name or a list) matches calls by their gate alone and
    ignores ``success``, so an approved write that failed still proves the
    approval. ``count`` asks for exactly that many matching calls; 0 proves the
    tool did not run. ``turn`` (1-based) limits the match to the calls of one turn,
    which is how a scenario shows a write did not run before its confirm step.
    """
    expected = scenario.get("expected_tools")
    if not expected:
        return None
    calls = _collect_tool_calls(ze_result)

    for entry in expected:
        if isinstance(entry, str):
            entry = {"name": entry}
        matching = [tc for tc in calls if _counts(tc, entry)]
        expected_args = entry.get("args")
        if expected_args:
            matching = [
                tc for tc in matching if _match_args(tc.get("args", {}), expected_args)
            ]
        count = entry.get("count")
        if count is None:
            if not matching:
                return False
        elif len(matching) != count:
            return False

    return True


def _gate(call: dict) -> str:
    return call.get("gate") or ("parked" if call.get("parked") else "none")


def _counts(call: dict, entry: dict) -> bool:
    if call.get("tool_name") != entry["name"]:
        return False
    if entry.get("turn") is not None and call.get("turn") != entry["turn"]:
        return False
    gate = _gate(call)
    wanted = entry.get("gate")
    if wanted is not None:
        return gate in ([wanted] if isinstance(wanted, str) else wanted)
    if gate == "parked":
        return bool(entry.get("allow_parked"))
    return bool(call.get("success")) and gate not in _DID_NOT_RUN


def outcome_correct(verify_results: list[VerifyResult]) -> bool | None:
    """True only if every DB verification check passed."""
    if not verify_results:
        return None
    return all(r.passed for r in verify_results)


def _collect_tool_calls(ze_result: dict) -> list[dict]:
    turns = ze_result.get("turns")
    if turns:
        calls: list[dict] = []
        for idx, turn in enumerate(turns, start=1):
            number = turn.get("turn", idx)
            calls.extend(
                {**call, "turn": number}
                for call in turn["result"].get("tool_calls", [])
            )
        return calls
    return [{**call, "turn": 1} for call in ze_result.get("tool_calls", [])]


def _match_args(actual: dict, expected_args: dict) -> bool:
    for key, value in expected_args.items():
        if key.endswith("__icontains"):
            col = key[: -len("__icontains")]
            actual_val = actual.get(col)
            if actual_val is None or str(value).lower() not in str(actual_val).lower():
                return False
        elif key.endswith("__contains"):
            col = key[: -len("__contains")]
            actual_val = actual.get(col)
            if actual_val is None or str(value) not in str(actual_val):
                return False
        elif key.endswith("__gte"):
            col = key[: -len("__gte")]
            actual_val = actual.get(col)
            if actual_val is None or str(actual_val) < str(value):
                return False
        elif key.endswith("__lte"):
            col = key[: -len("__lte")]
            actual_val = actual.get(col)
            if actual_val is None or str(actual_val) > str(value):
                return False
        else:
            if actual.get(key) != value:
                return False
    return True
