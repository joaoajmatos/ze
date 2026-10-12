from ze_eval.scoring import tools_correct

_DRAFT = {
    "tool_calls": [
        {"tool_name": "create_goal", "args": {}, "success": False, "is_draft": True}
    ]
}
_OK = {"tool_calls": [{"tool_name": "create_goal", "args": {}, "success": True}]}
_FAILED = {"tool_calls": [{"tool_name": "create_goal", "success": False}]}


def test_draft_not_counted_by_default():
    assert tools_correct({"expected_tools": ["create_goal"]}, _DRAFT) is False


def test_draft_not_counted_for_dict_entry_without_flag():
    assert tools_correct({"expected_tools": [{"name": "create_goal"}]}, _DRAFT) is False


def test_allow_draft_counts_draft():
    scenario = {"expected_tools": [{"name": "create_goal", "allow_draft": True}]}
    assert tools_correct(scenario, _DRAFT) is True


def test_allow_draft_still_accepts_real_call():
    scenario = {"expected_tools": [{"name": "create_goal", "allow_draft": True}]}
    assert tools_correct(scenario, _OK) is True


def test_allow_draft_does_not_excuse_plain_failure():
    scenario = {"expected_tools": [{"name": "create_goal", "allow_draft": True}]}
    assert tools_correct(scenario, _FAILED) is False


def test_allow_draft_still_checks_args():
    scenario = {
        "expected_tools": [
            {"name": "create_goal", "allow_draft": True, "args": {"goal_type": "x"}}
        ]
    }
    assert tools_correct(scenario, _DRAFT) is False
