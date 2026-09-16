from __future__ import annotations

from unittest.mock import patch

from ze_automation.migrations.versions import zc030_goal_learning_claims as zc030


def test_revision_chain():
    assert zc030.revision == "zc030"
    assert zc030.down_revision == "zc029"


def test_upgrade_creates_claim_tables_and_drops_legacy():
    with patch.object(zc030, "op") as mock_op:
        zc030.upgrade()

    executed = [call.args[0] for call in mock_op.execute.call_args_list]
    joined = "\n".join(executed)
    assert "CREATE TABLE goal_learning_claims" in joined
    assert "CREATE TABLE goal_learning_evidence" in joined
    assert "CREATE TABLE goal_learning_reviews" in joined
    assert "CREATE TABLE goal_learning_relationships" in joined
    assert "CREATE TABLE goal_learning_promotions" in joined
    assert "DROP COLUMN IF EXISTS learnings" in joined
    assert "DROP TABLE IF EXISTS goal_learnings" in joined
    assert "INSERT INTO goal_learning_claims" in joined
    assert "review_needed" in joined


def test_downgrade_is_hard_cut():
    with patch.object(zc030, "op"):
        try:
            zc030.downgrade()
        except NotImplementedError:
            return
        raise AssertionError("downgrade must hard-cut")
