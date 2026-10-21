import pytest

from ze_memory.action_records.errors import UnknownActionSubjectKindError
from ze_memory.action_records.types import ActionSubjectKind, subject_context_key


def test_every_kind_maps_to_one_context_key():
    assert {k.value: subject_context_key(k) for k in ActionSubjectKind} == {
        "goal": "goal_id",
        "workflow": "workflow_id",
        "workflow_run": "workflow_run_id",
        "workspace_run": "workspace_run_id",
    }


def test_the_map_is_closed():
    with pytest.raises(UnknownActionSubjectKindError):
        subject_context_key("channel")
