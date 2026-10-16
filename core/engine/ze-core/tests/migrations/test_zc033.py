from __future__ import annotations

from unittest.mock import patch

from ze_core.migrations.versions import zc033_drop_routing_log_tier as zc033


def test_revision_chain():
    assert zc033.revision == "zc033"
    assert zc033.down_revision == "zc032"


def test_upgrade_drops_both_columns():
    with patch.object(zc033, "op") as mock_op:
        zc033.upgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "DROP COLUMN IF EXISTS complexity" in executed
    assert "DROP COLUMN IF EXISTS model_selected" in executed


def test_downgrade_re_adds_both_as_nullable_text():
    with patch.object(zc033, "op") as mock_op:
        zc033.downgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "ADD COLUMN IF NOT EXISTS complexity TEXT NULL" in executed
    assert "ADD COLUMN IF NOT EXISTS model_selected TEXT NULL" in executed
