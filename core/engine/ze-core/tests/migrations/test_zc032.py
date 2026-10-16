from __future__ import annotations

from unittest.mock import patch

from ze_core.migrations.versions import zc032_message_rollback as zc032


def test_revision_chain():
    assert zc032.revision == "zc032"
    assert zc032.down_revision == "zc031"


def test_upgrade_adds_rollback_column():
    with patch.object(zc032, "op") as mock_op:
        zc032.upgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "ADD COLUMN IF NOT EXISTS rollback JSONB NULL" in executed


def test_downgrade_drops_column():
    with patch.object(zc032, "op") as mock_op:
        zc032.downgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "DROP COLUMN IF EXISTS rollback" in executed
