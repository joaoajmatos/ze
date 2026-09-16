from __future__ import annotations

from unittest.mock import patch

from ze_memory.migrations.versions import zm023_procedure_activation as zm023


def test_revision_chain():
    assert zm023.revision == "zm023"
    assert zm023.down_revision == "zm022"


def test_upgrade_creates_activation_tables():
    with patch.object(zm023, "op") as mock_op:
        zm023.upgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "CREATE TABLE procedure_invocations" in executed
    assert "CREATE TABLE procedure_action_links" in executed
    assert "CREATE TABLE procedure_activation_feedback" in executed
