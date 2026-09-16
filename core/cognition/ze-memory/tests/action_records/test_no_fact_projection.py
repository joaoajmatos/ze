from __future__ import annotations

import inspect

from ze_memory.action_records.contribution import submit_action_record
from ze_memory.retriever import PostgresMemoryStore


def test_submit_action_record_does_not_call_fact_writers() -> None:
    source = inspect.getsource(submit_action_record)
    assert "_write_fact_with_contradiction_check" not in source
    assert "propose_facts" not in source
    assert "memory_facts" not in source


def test_memory_store_has_no_action_record_fact_projection() -> None:
    assert not hasattr(PostgresMemoryStore, "append_action_record")
    write_src = inspect.getsource(
        PostgresMemoryStore._write_fact_with_contradiction_check
    )
    assert "ACTION_RECORD" not in write_src
    assert "action_records" not in write_src
