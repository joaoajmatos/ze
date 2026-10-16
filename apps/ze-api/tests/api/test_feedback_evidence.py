"""Feedback is reconstructable evidence tied to the trace; never a fact (Phase 165 US2)."""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import asdict
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_core.conversation.messages.store import PostgresMessageStore
from ze_core.conversation.messages.types import (
    CompactionTrace,
    JudgmentTrace,
    MemoryChunkTrace,
    MessageTrace,
    SkillUsageTrace,
    ToolCallTrace,
)
from ze_memory.feedback_records import (
    FeedbackKind,
    FeedbackRecordDraft,
    PostgresFeedbackStore,
    feedback_contribution,
    submit_feedback_record,
)

ROOT = pathlib.Path(__file__).resolve().parents[4]


def _full_trace() -> MessageTrace:
    return MessageTrace(
        agent="research",
        routing_method="embedding",
        confidence=0.8,
        score_gap=0.2,
        is_compound=False,
        subtasks=[],
        memory_chunks=[MemoryChunkTrace(text="f", score=0.7, source="fact")],
        tool_calls=[
            ToolCallTrace(
                name="web_search",
                result_snippet="",
                duration_ms=3,
                success=True,
                access="read",
            )
        ],
        skills_used=[
            SkillUsageTrace(
                skill_id="s", name="n", source="bundled", trigger="explicit"
            )
        ],
        conductor_ledger=[{"agent": "research", "status": "done"}],
        judgments=[
            JudgmentTrace(question_id="speech_act", kind="choice", latency_ms=5),
            JudgmentTrace(question_id="routing_choice", kind="choice", latency_ms=6),
            JudgmentTrace(
                question_id="needs_deep_reasoning", kind="noul", latency_ms=7
            ),
        ],
        compaction=CompactionTrace(span_start=0, span_end=4),
        resume_recap_applied=True,
        effects_known=True,
    )


class _Pool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _Ctx:
            async def __aenter__(self_inner):
                return conn

            async def __aexit__(self_inner, *a):
                return None

        return _Ctx()


async def test_feedback_message_id_reaches_the_whole_trace():
    message_id = uuid4()
    trace = _full_trace()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"trace": json.dumps(asdict(trace))})
    got = await PostgresMessageStore(_Pool(conn)).get_trace(message_id)
    assert got == trace
    assert [j.question_id for j in got.judgments] == [
        "speech_act",
        "routing_choice",
        "needs_deep_reasoning",
    ]
    assert got.memory_chunks and got.tool_calls and got.skills_used
    assert got.conductor_ledger and got.compaction is not None
    assert "WHERE id = $1" in conn.fetchrow.call_args[0][0]


async def test_record_holds_only_ids_never_the_trace_or_content():
    draft = FeedbackRecordDraft(
        idempotency_key="k",
        message_id=uuid4(),
        thread_id="t",
        kind=FeedbackKind.THUMBS_DOWN,
        occurred_at=datetime.now(timezone.utc),
        trace_present=True,
    )
    conn = AsyncMock()
    row = {
        "id": uuid4(),
        "idempotency_key": "k",
        "message_id": draft.message_id,
        "thread_id": "t",
        "kind": "thumbs_down",
        "occurred_at": draft.occurred_at,
        "provenance": "prompt_supplied",
        "confidence": 1.0,
        "target_face": "world",
        "trace_present": True,
        "created_at": draft.occurred_at,
    }
    conn.fetchrow = AsyncMock(return_value=row)
    store = PostgresFeedbackStore(_Pool(conn))
    record = await submit_feedback_record(store, feedback_contribution(draft))
    assert set(vars(record)) == {
        "id", "idempotency_key", "message_id", "thread_id", "kind",
        "occurred_at", "provenance", "confidence", "target_face",
        "trace_present", "created_at",
    }  # fmt: skip


# ── Guard tests (T028): feedback is capture-only ─────────────────────────────

_ENGINE_DIRS = [
    "core/engine/ze-core/ze_core",
    "core/cognition/ze-memory/ze_memory/retriever.py",
    "core/cognition/ze-memory/ze_memory/policies.py",
    "core/cognition/ze-memory/ze_memory/extractor.py",
    "core/cognition/ze-memory/ze_memory/admission.py",
    "core/cognition/ze-memory/ze_memory/speech_act_judge.py",
    "core/cognition/ze-memory/ze_memory/composite.py",
    "core/arbitration/ze-priority/ze_priority",
    "core/contracts/ze-agents/ze_agents",
]
_FEEDBACK = re.compile(r"feedback_records|FeedbackStore|feedback_store|FEEDBACK_RECORD")


def _py_files(rel: str):
    p = ROOT / rel
    return [p] if p.is_file() else sorted(p.rglob("*.py"))


def test_no_engine_routing_admission_prompt_or_ranking_module_reads_feedback():
    offenders = []
    for rel in _ENGINE_DIRS:
        for path in _py_files(rel):
            if "migrations" in path.parts:
                continue
            if _FEEDBACK.search(path.read_text()):
                offenders.append(str(path.relative_to(ROOT)))
    # claims.py (ClaimKind) and errors.py (exception types) only define vocabulary.
    vocabulary = ("ze_agents/claims.py", "ze_agents/errors.py")
    assert [o for o in offenders if not o.endswith(vocabulary)] == []


def test_turn_graph_config_has_no_feedback_store():
    text = (ROOT / "core/engine/ze-core/ze_core/container.py").read_text()
    assert "feedback" not in text.lower()
    api = (ROOT / "apps/ze-api/ze_api/container.py").read_text()
    # exposed on the container for routes only; never in a configurable/dep map
    for line in api.splitlines():
        if "feedback_store" in line or "FeedbackStore" in line:
            assert "configurable" not in line
    assert "FeedbackStore:" not in api


def test_feedback_package_never_imports_fact_or_retrieval_paths():
    pkg = ROOT / "core/cognition/ze-memory/ze_memory/feedback_records"
    for path in pkg.rglob("*.py"):
        text = path.read_text()
        for banned in ("retriever", "memory_facts", "propose_facts", "embedder"):
            assert banned not in text, (path.name, banned)


def test_no_module_other_than_feedback_surface_writes_to_feedback_records():
    allowed = {
        "core/cognition/ze-memory/ze_memory/feedback_records/store.py",
        "core/cognition/ze-memory/ze_memory/migrations/versions/zm024_feedback_records.py",
    }
    for base in ("core", "plugins", "apps/ze-api/ze_api", "integrations"):
        for path in (ROOT / base).rglob("*.py"):
            rel = str(path.relative_to(ROOT))
            if "/tests/" in rel or rel in allowed or ".venv" in rel:
                continue
            text = path.read_text()
            assert not re.search(
                r"(INSERT INTO|UPDATE|DELETE FROM)\s+feedback_records", text
            ), rel


def test_message_trace_clearing_paths_do_not_exist():
    # R6: no code path clears or rewrites messages.trace except save_trace.
    hits = []
    for base in ("core", "plugins", "apps/ze-api/ze_api"):
        for path in (ROOT / base).rglob("*.py"):
            rel = str(path.relative_to(ROOT))
            if "/tests/" in rel or ".venv" in rel:
                continue
            for m in re.finditer(
                r"UPDATE messages SET trace|trace = NULL", path.read_text()
            ):
                hits.append(rel)
    assert sorted(set(hits)) == [
        "core/engine/ze-core/ze_core/conversation/messages/store.py"
    ]
