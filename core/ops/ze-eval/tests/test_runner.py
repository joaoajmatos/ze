from ze_eval.runner import collect_tool_calls


def test_collects_tool_calls_from_every_turn_in_order():
    turns = [
        {
            "turn": 1,
            "prompt": "find the file",
            "result": {"tool_calls": [{"tool_name": "search", "success": True}]},
        },
        {
            "turn": 2,
            "prompt": "email it",
            "result": {
                "tool_calls": [{"tool_name": "send_email", "is_draft": True}],
                "pending_confirmation": True,
            },
        },
    ]

    calls = collect_tool_calls(turns)

    assert [c["tool_name"] for c in calls] == ["search", "send_email"]
    assert [c["turn"] for c in calls] == [1, 2]


def test_collect_skips_turns_without_tool_calls():
    turns = [
        {"turn": 1, "prompt": "hello", "result": {}},
        {
            "turn": 2,
            "prompt": "now search",
            "result": {"tool_calls": [{"tool_name": "search"}]},
        },
    ]

    calls = collect_tool_calls(turns)

    assert [c["tool_name"] for c in calls] == ["search"]
    assert [c["turn"] for c in calls] == [2]


def test_collect_does_not_mutate_the_source_calls():
    original = {"tool_name": "search", "success": True}
    turns = [{"turn": 1, "prompt": "p", "result": {"tool_calls": [original]}}]

    collect_tool_calls(turns)

    assert "turn" not in original


def test_collect_returns_empty_for_no_turns():
    assert collect_tool_calls([]) == []
