from __future__ import annotations

from unittest.mock import patch

from ze_core.migrations.versions import zc035_drop_routing_log_tier as zc035


def test_revision_chain():
    assert zc035.revision == "zc035"
    assert zc035.down_revision == "zc034"


def test_upgrade_drops_both_columns():
    with patch.object(zc035, "op") as mock_op:
        zc035.upgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "DROP COLUMN IF EXISTS complexity" in executed
    assert "DROP COLUMN IF EXISTS model_selected" in executed


def test_downgrade_re_adds_both_as_nullable_text():
    with patch.object(zc035, "op") as mock_op:
        zc035.downgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "ADD COLUMN IF NOT EXISTS complexity TEXT NULL" in executed
    assert "ADD COLUMN IF NOT EXISTS model_selected TEXT NULL" in executed
