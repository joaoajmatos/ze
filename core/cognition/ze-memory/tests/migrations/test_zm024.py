from __future__ import annotations

from unittest.mock import patch

from ze_memory.migrations.versions import zm024_feedback_records as zm024


def test_revision_chain():
    assert zm024.revision == "zm024"
    assert zm024.down_revision == "zm023"


def test_upgrade_creates_append_only_ledger():
    with patch.object(zm024, "op") as mock_op:
        zm024.upgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "CREATE TABLE feedback_records" in executed
    assert "idempotency_key TEXT NOT NULL UNIQUE" in executed
    assert "'thumbs_up', 'thumbs_down', 'cleared', 'retry_requested'" in executed
    assert "provenance IN" in executed
    assert "confidence >= 0 AND confidence <= 1" in executed
    assert "(message_id, occurred_at DESC)" in executed
    assert "REFERENCES" not in executed
    assert "content" not in executed


def test_downgrade_drops_table():
    with patch.object(zm024, "op") as mock_op:
        zm024.downgrade()
    assert "DROP TABLE IF EXISTS feedback_records" in mock_op.execute.call_args.args[0]
