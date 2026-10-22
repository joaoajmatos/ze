"""Scenario `setup:` rows (phase 195).

A scenario that points the screen at a record needs that record to exist. `setup:` lists rows to
insert before the scenario and delete after it, in reverse order, bound to names so `context:` and
`turns` can say `{{wf.id}}`. ze-eval has no Ze deps and the Ze API has no create route for most of
these records, so rows go in through the same DB connection the verifier uses, into the tables below
only, with every NOT NULL column filled. Run evals against a throwaway database.

    setup:
      - {kind: workflow, name: wf, fields: {name: "Weekly report"}}
      - {kind: workflow_execution, name: run, parent: wf, fields: {status: failed}}
    context:
      subject:
        - {kind: workflow_execution, id: "{{run.id}}", parent_id: "{{wf.id}}"}
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

import asyncpg

_REF = re.compile(r"\{\{\s*(\w+)\.(\w+)\s*\}\}")


class FixtureError(ValueError):
    """A `setup:` item could not be created."""


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Kind:
    table: str
    defaults: Callable[[str], dict[str, Any]]
    id_column: str = "id"
    parent_column: str | None = None
    # Value the screen ref carries as `id` when it is not the row's id column.
    ref: Callable[[dict[str, Any]], str] | None = None


KINDS: dict[str, Kind] = {
    "goal": Kind(
        "goals",
        lambda n: {
            "title": n,
            "objective": "Eval objective",
            "success_condition": "Eval done",
            "status": "active",
        },
    ),
    "goal_gate": Kind(
        "goal_gates",
        lambda n: {
            "after_sequence": 1,
            "title": n,
            "status": "awaiting_approval",
            "fired_at": _now(),
        },
        parent_column="goal_id",
    ),
    "workflow": Kind(
        "workflows", lambda n: {"name": n, "description": "Eval workflow", "steps": []}
    ),
    "workflow_execution": Kind(
        "workflow_executions",
        lambda n: {
            "status": "failed",
            "error": "timeout",
            "started_at": _now() - timedelta(minutes=2),
            "completed_at": _now() - timedelta(minutes=1),
        },
        parent_column="workflow_id",
    ),
    "loop": Kind(
        "open_loops",
        lambda n: {
            "title": n,
            "provenance": "conversation",
            "confidence": 0.6,
            "state": "active",
        },
    ),
    "held_write": Kind(
        "held_writes",
        lambda n: {
            "request_id": f"eval-{uuid.uuid4().hex}",
            "source": "workflow",
            "owner_ref": "eval",
            "items": [{"effect_phrase": "send an email", "summary": n}],
            "payload": {},
            "expires_at": _now() + timedelta(days=1),
        },
        id_column="request_id",
    ),
    "notification": Kind(
        "notifications",
        lambda n: {
            "event_type": "workflow_failure",
            "source": "workflows",
            "title": n,
            "body": "Eval notification",
            "push_class": "discretionary",
            "urgency": "normal",
            "delivery": "delivered",
        },
    ),
    "entity": Kind(
        "memory_entities", lambda n: {"entity_type": "person", "canonical_name": n}
    ),
    "fact": Kind(
        "memory_facts",
        lambda n: {
            "predicate": "eval_preference",
            "value": n,
            "provenance": "prompt_supplied",
            "claim_kind": "fact",
        },
    ),
    "procedure": Kind(
        "procedure_identities", lambda n: {"canonical_name": n, "status": "active"}
    ),
    "skill": Kind(
        "skills",
        lambda n: {
            "name": n,
            "slug": re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")
            + "-"
            + uuid.uuid4().hex[:6],
            "description": "Eval skill",
            "instructions": "Do the thing.",
            "source": "imported",
            "content_hash": uuid.uuid4().hex,
        },
    ),
    "workspace_run": Kind(
        "workspace_runs", lambda n: {"command": n, "origin": "conversation"}
    ),
    "hypothesis": Kind(
        "correlation_hypothesis",
        lambda n: {
            "id": uuid.uuid4(),
            "summary": n,
            "narrative": "Eval narrative",
            "relation": "pattern",
            "confidence": 0.4,
            "relevance": 0.5,
            "evidence": [],
            "entities": [],
            "claim_kind": "suspicion",
        },
    ),
    "contact": Kind(
        "contacts",
        lambda n: {"name": n, "claim_kind": "identity", "provenance": "synthesized"},
    ),
    "reminder": Kind(
        "user_reminders", lambda n: {"label": n, "fire_at": _now() + timedelta(days=1)}
    ),
    "news_article": Kind(
        "news_articles",
        lambda n: {
            "url": f"https://eval.example/{uuid.uuid4().hex}",
            "source_key": "eval",
            "title": n,
            "published_at": _now() - timedelta(days=1),
        },
        id_column="url",
        ref=lambda row: hashlib.md5(
            row["url"].encode("utf-8"), usedforsecurity=False
        ).hexdigest(),
    ),
}


def substitute(value: Any, bindings: dict[str, dict[str, Any]]) -> Any:
    """Replace `{{name.field}}` in every string of a nested structure. Unknown names raise."""
    if isinstance(value, str):

        def _sub(match: re.Match[str]) -> str:
            name, key = match.groups()
            if name not in bindings or key not in bindings[name]:
                raise FixtureError(
                    f"{{{{{name}.{key}}}}} names nothing created by setup"
                )
            return str(bindings[name][key])

        return _REF.sub(_sub, value)
    if isinstance(value, dict):
        return {k: substitute(v, bindings) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, bindings) for v in value]
    return value


def _param(value: Any) -> tuple[Any, str]:
    """A bound value and the cast that goes with it."""
    if isinstance(value, (dict, list)):
        return json.dumps(value), "::jsonb"
    return value, ""


@dataclass
class Fixtures:
    conn: asyncpg.Connection
    bindings: dict[str, dict[str, Any]] = field(default_factory=dict)
    _created: list[tuple[Kind, Any]] = field(default_factory=list)

    @classmethod
    async def create(cls, items: list[dict], db_url: str | None = None) -> Fixtures:
        url = db_url or os.environ.get(
            "DATABASE_URL", "postgresql://ze:ze@localhost:5432/ze"
        )
        fixtures = cls(await asyncpg.connect(url))
        try:
            for item in items:
                await fixtures._insert(item)
        except Exception:
            await fixtures.delete()
            raise
        return fixtures

    async def _insert(self, item: dict) -> None:
        kind_name = item.get("kind")
        kind = KINDS.get(kind_name)
        if kind is None:
            raise FixtureError(
                f"unknown setup kind {kind_name!r}; known: {', '.join(sorted(KINDS))}"
            )
        name = item.get("name")
        if not name or not re.fullmatch(r"\w+", str(name)):
            raise FixtureError(
                f"setup item {kind_name!r} needs a name made of letters, digits and _"
            )
        if name in self.bindings:
            raise FixtureError(f"setup name {name!r} is used twice")
        values = kind.defaults(
            str(
                item.get("fields", {}).get("title")
                or item.get("fields", {}).get("name")
                or name
            )
        )
        values.update(substitute(item.get("fields") or {}, self.bindings))
        if kind.parent_column and kind.parent_column not in values:
            parent = item.get("parent")
            if parent not in self.bindings:
                raise FixtureError(
                    f"{kind_name} {name!r} needs `parent:` naming an earlier item"
                )
            values[kind.parent_column] = self.bindings[parent]["id"]
        columns = list(values)
        params, casts = zip(*(_param(values[c]) for c in columns))
        placeholders = ", ".join(f"${i + 1}{cast}" for i, cast in enumerate(casts))
        sql = f"INSERT INTO {kind.table} ({', '.join(columns)}) VALUES ({placeholders}) RETURNING {kind.id_column}"
        try:
            row_id = await self.conn.fetchval(sql, *params)
        except Exception as exc:
            raise FixtureError(f"setup {kind_name} {name!r} failed: {exc}") from exc
        self._created.append((kind, row_id))
        bound = {**values, "id": row_id}
        if kind.ref is not None:
            bound["id"] = kind.ref(values)
        self.bindings[name] = {
            k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in bound.items()
        }

    async def delete(self) -> None:
        """Remove every created row, newest first, and close the connection. Never raises."""
        for kind, row_id in reversed(self._created):
            try:
                await self.conn.execute(
                    f"DELETE FROM {kind.table} WHERE {kind.id_column} = $1", row_id
                )
            except Exception:
                pass
        self._created.clear()
        await self.conn.close()
