from __future__ import annotations

from unittest.mock import patch

from ze_personal.migrations.versions import zc040_channel_poll_outcome as zc040


def test_revision_chain():
    assert zc040.revision == "zc040"
    assert zc040.down_revision == "zc039"


def test_upgrade_adds_the_two_nullable_columns():
    with patch.object(zc040, "op") as mock_op:
        zc040.upgrade()

    sql = " ".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "user_channel_watermarks" in sql
    assert "last_outcome" in sql and "last_outcome_at" in sql
    assert "NOT NULL" not in sql


def test_downgrade_drops_both_columns():
    with patch.object(zc040, "op") as mock_op:
        zc040.downgrade()

    sql = " ".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "DROP COLUMN" in sql
    assert "last_outcome_at" in sql and "last_outcome" in sql
