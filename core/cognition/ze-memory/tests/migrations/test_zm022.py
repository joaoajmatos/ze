from __future__ import annotations

from unittest.mock import patch

from ze_memory.migrations.versions import zm022_procedure_lifecycle as zm022


def test_revision_chain():
    assert zm022.revision == "zm022"
    assert zm022.down_revision == "zm021"


def test_upgrade_drops_memory_procedures():
    with patch.object(zm022, "op") as mock_op:
        zm022.upgrade()
    executed = "\n".join(call.args[0] for call in mock_op.execute.call_args_list)
    assert "CREATE TABLE procedure_identities" in executed
    assert "CREATE TABLE procedure_candidates" in executed
    assert "DROP TABLE IF EXISTS memory_procedures" in executed
    assert "needs_review" in executed
