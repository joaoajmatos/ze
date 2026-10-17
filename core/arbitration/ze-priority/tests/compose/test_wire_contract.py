"""Every composed component must satisfy the exported UI schema, or the client drops the whole tree."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from ze_components.schema import export_json_schema
from ze_components.serialize import serialize_primitive
from ze_priority.compose import rules
from ze_priority.compose.types import SourceSnapshot, WorkflowDigest
from ze_worldstate.types import LoopState

from tests.compose.test_rules_topic import FakeEmbedder, _execution, _workflow
from tests.factories import make_goal_progress, make_held_write, make_loop

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
SCHEMA = export_json_schema()
DEFS = SCHEMA["$defs"]


def _check(value: Any, node: dict, path: str) -> None:
    if "$ref" in node:
        _check(value, DEFS[node["$ref"].rsplit("/", 1)[1]], path)
        return
    if "oneOf" in node:
        mapping = node["discriminator"]["mapping"]
        _check(value, DEFS[mapping[value["type"]].rsplit("/", 1)[1]], path)
        return
    if node.get("type") == "object" or "properties" in node:
        props = node["properties"]
        extra = set(value) - set(props)
        assert not extra, f"{path}: unknown keys {extra}"
        missing = set(node.get("required", [])) - set(value)
        assert not missing, f"{path}: missing required {missing}"
        for key, item in value.items():
            _check(item, props[key], f"{path}.{key}")
    elif node.get("type") == "array":
        for i, item in enumerate(value):
            _check(item, node["items"], f"{path}[{i}]")
    elif "enum" in node:
        assert value in node["enum"], f"{path}: {value!r} not in {node['enum']}"
    elif "const" in node:
        assert value == node["const"], path


def _validate(draft) -> None:
    assert draft.components
    for i, component in enumerate(draft.components):
        _check(serialize_primitive(component), {"$ref": "#/$defs/Primitive"}, f"c{i}")


def test_slipping_composition_matches_the_schema():
    snapshot = SourceSnapshot(
        loops=[
            make_loop(state=LoopState.DRIFTING, drift_deadline=NOW - timedelta(days=2)),
            make_loop(state=LoopState.ACTIVE, drift_deadline=NOW + timedelta(days=3)),
        ],
        goals=[make_goal_progress(stuck_since=NOW - timedelta(days=9))],
    )
    _validate(rules.slipping(snapshot, NOW))


def test_decisions_composition_matches_the_schema_including_held_writes_without_a_kind():
    snapshot = SourceSnapshot(
        loops=[make_loop(state=LoopState.SUSPECTED)],
        goals=[
            make_goal_progress(
                goal_overrides={"status": "awaiting_gate"},
                gate_id=uuid4(),
                gate_title="Approve",
                gate_open_since=NOW - timedelta(days=2),
            )
        ],
        held_writes=[make_held_write(expires_at=NOW + timedelta(hours=5))],
    )
    draft = rules.decisions(snapshot, NOW)
    _validate(draft)
    held = next(
        c
        for c in draft.components
        if getattr(c, "claim", None) and c.claim.subject == "held_write"
    )
    assert "kind" not in serialize_primitive(held)["claim"]


def test_topic_composition_matches_the_schema_including_workflows():
    snapshot = SourceSnapshot(
        loops=[make_loop(title="LedgerLite launch", state=LoopState.ACTIVE)],
        goals=[],
        workflows=[
            WorkflowDigest(_workflow(), _execution("failed", error="timed out")),
            WorkflowDigest(_workflow("LedgerLite launch off", enabled=False), None),
        ],
    )
    _validate(rules.topic(snapshot, "ledgerlite launch", FakeEmbedder(), NOW))
