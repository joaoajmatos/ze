import pytest

from ze_eval.scoring import tools_correct


def _call(gate="none", success=True, **extra):
    return {
        "tool_name": "create_goal",
        "args": {},
        "success": success,
        "gate": gate,
        "parked": gate == "parked",
        **extra,
    }


_PARKED = {"tool_calls": [_call("parked")]}
_OK = {"tool_calls": [_call()]}
_APPROVED = {"tool_calls": [_call("approved")]}
_FAILED = {"tool_calls": [_call(success=False)]}


def test_parked_call_not_counted_by_default():
    assert tools_correct({"expected_tools": ["create_goal"]}, _PARKED) is False


def test_parked_call_not_counted_for_dict_entry_without_flag():
    assert tools_correct({"expected_tools": [{"name": "create_goal"}]}, _PARKED) is False


def test_allow_parked_counts_parked():
    scenario = {"expected_tools": [{"name": "create_goal", "allow_parked": True}]}
    assert tools_correct(scenario, _PARKED) is True


def test_allow_parked_still_accepts_real_call():
    scenario = {"expected_tools": [{"name": "create_goal", "allow_parked": True}]}
    assert tools_correct(scenario, _OK) is True


def test_allow_parked_does_not_excuse_plain_failure():
    scenario = {"expected_tools": [{"name": "create_goal", "allow_parked": True}]}
    assert tools_correct(scenario, _FAILED) is False


def test_allow_parked_still_checks_args():
    scenario = {
        "expected_tools": [
            {"name": "create_goal", "allow_parked": True, "args": {"goal_type": "x"}}
        ]
    }
    assert tools_correct(scenario, _PARKED) is False


def test_approved_call_counts_as_executed_by_default():
    assert tools_correct({"expected_tools": ["create_goal"]}, _APPROVED) is True


@pytest.mark.parametrize("gate", ["denied", "expired", "refused_over_cap"])
def test_calls_that_did_not_run_are_not_counted(gate):
    result = {"tool_calls": [_call(gate)]}
    assert tools_correct({"expected_tools": ["create_goal"]}, result) is False


def test_gate_filter_matches_only_that_gate():
    parked = {"expected_tools": [{"name": "create_goal", "gate": "parked"}]}
    approved = {"expected_tools": [{"name": "create_goal", "gate": "approved"}]}

    assert tools_correct(parked, _PARKED) is True
    assert tools_correct(approved, _PARKED) is False
    assert tools_correct(approved, _APPROVED) is True


def test_gate_filter_ignores_success_so_a_failed_approved_call_still_proves_the_gate():
    result = {"tool_calls": [_call("approved", success=False)]}
    scenario = {"expected_tools": [{"name": "create_goal", "gate": "approved"}]}

    assert tools_correct(scenario, result) is True


def test_gate_filter_accepts_a_list():
    scenario = {"expected_tools": [{"name": "create_goal", "gate": ["none", "approved"]}]}

    assert tools_correct(scenario, _OK) is True
    assert tools_correct(scenario, _APPROVED) is True
    assert tools_correct(scenario, _PARKED) is False


def test_count_requires_exactly_that_many_matches():
    result = {"tool_calls": [_call("approved"), _call("approved")]}
    once = {"expected_tools": [{"name": "create_goal", "gate": "approved", "count": 1}]}
    twice = {"expected_tools": [{"name": "create_goal", "gate": "approved", "count": 2}]}

    assert tools_correct(once, result) is False
    assert tools_correct(twice, result) is True


def test_count_zero_proves_a_tool_did_not_run():
    scenario = {
        "expected_tools": [
            {"name": "create_goal", "gate": ["none", "approved"], "count": 0}
        ]
    }

    assert tools_correct(scenario, _PARKED) is True
    assert tools_correct(scenario, _APPROVED) is False


def test_calls_are_counted_across_turns():
    result = {
        "turns": [
            {"turn": 1, "result": {"tool_calls": [_call("parked")]}},
            {"turn": 2, "result": {"tool_calls": [_call("approved")]}},
        ]
    }
    scenario = {
        "expected_tools": [
            {"name": "create_goal", "gate": "parked", "count": 1},
            {"name": "create_goal", "gate": "approved", "count": 1},
        ]
    }

    assert tools_correct(scenario, result) is True


def test_turn_filter_limits_matches_to_one_turn():
    result = {
        "turns": [
            {"turn": 1, "result": {"tool_calls": [_call("parked")]}},
            {"turn": 2, "result": {"tool_calls": [_call("approved")]}},
        ]
    }
    ran = ["none", "approved", "pre_approved"]
    before = {
        "expected_tools": [
            {"name": "create_goal", "gate": ran, "turn": 1, "count": 0},
        ]
    }
    after = {
        "expected_tools": [
            {"name": "create_goal", "gate": ran, "turn": 2, "count": 1},
        ]
    }
    wrong_turn = {
        "expected_tools": [{"name": "create_goal", "gate": "parked", "turn": 2}]
    }

    assert tools_correct(before, result) is True
    assert tools_correct(after, result) is True
    assert tools_correct(wrong_turn, result) is False


def test_turn_filter_on_a_single_turn_scenario_means_turn_one():
    scenario = {"expected_tools": [{"name": "create_goal", "gate": "parked", "turn": 1}]}

    assert tools_correct(scenario, _PARKED) is True
