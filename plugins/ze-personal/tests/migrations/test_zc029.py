from __future__ import annotations

from unittest.mock import patch

from ze_personal.migrations.versions import zc029_drop_contact_relationships as zc029


def test_revision_chain():
    assert zc029.revision == "zc029"
    assert zc029.down_revision == "zc028"


def test_upgrade_drops_contact_relationships_cleanly():
    with patch.object(zc029, "op") as mock_op:
        zc029.upgrade()

    executed = [call.args[0] for call in mock_op.execute.call_args_list]
    assert any("DROP TABLE contact_relationships" in stmt for stmt in executed)
    # No data-preserving statement (backfill/copy) — empty-table clean drop.
    assert not any("INSERT INTO" in stmt for stmt in executed)


def test_downgrade_recreates_table():
    with patch.object(zc029, "op") as mock_op:
        zc029.downgrade()

    executed = [call.args[0] for call in mock_op.execute.call_args_list]
    assert any("CREATE TABLE contact_relationships" in stmt for stmt in executed)
