from __future__ import annotations

from unittest.mock import patch

from ze_core.migrations.versions import zc031_message_supersession as zc031


def test_revision_chain():
    assert zc031.revision == "zc031"
    assert zc031.down_revision == "zc030"


def test_upgrade_adds_supersession_columns_and_indexes():
    with patch.object(zc031, "op") as mock_op:
        zc031.upgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "ADD COLUMN IF NOT EXISTS replaces UUID NULL" in executed
    assert "ADD COLUMN IF NOT EXISTS replaced_by UUID NULL" in executed
    assert "messages_replaces_idx" in executed
    assert "messages_replaced_by_idx" in executed


def test_downgrade_drops_columns():
    with patch.object(zc031, "op") as mock_op:
        zc031.downgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "DROP COLUMN IF EXISTS replaced_by" in executed
    assert "DROP COLUMN IF EXISTS replaces" in executed
