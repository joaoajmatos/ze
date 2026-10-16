from ze_eval.scenario import load_scenarios


def test_load_scenarios_returns_list() -> None:
    scenarios = load_scenarios()
    assert isinstance(scenarios, list)
    assert len(scenarios) > 0
    assert "id" in scenarios[0]


def test_confirm_steps_follow_a_prompt_and_use_a_valid_choice() -> None:
    for scenario in load_scenarios():
        turns = scenario.get("turns") or []
        for i, turn in enumerate(turns):
            if "confirm" in turn:
                assert turn["confirm"] in {"approve", "deny"}, scenario["id"]
                assert "prompt" not in turn, scenario["id"]
                assert i > 0, scenario["id"]
            else:
                assert "prompt" in turn, scenario["id"]
                assert "edits" not in turn, scenario["id"]


def test_no_scenario_still_uses_the_removed_draft_flag() -> None:
    for scenario in load_scenarios():
        assert "allow_draft" not in str(scenario.get("expected_tools")), scenario["id"]


def test_write_confirmation_scenarios() -> None:
    scenarios = load_scenarios(tag="confirmation")
    by_id = {s["id"]: s for s in scenarios if s["file"] == "write_confirmation"}

    assert len(by_id) >= 5
    assert all("confirmation" in s["tags"] for s in by_id.values())
    assert all(s.get("criteria") for s in by_id.values())


def test_write_confirmation_scenarios_never_approve_a_send() -> None:
    for s in load_scenarios(tag="confirmation"):
        if s["file"] != "write_confirmation":
            continue
        text = str(s)
        sends_mail = "send_email" in text or "email" in s.get("description", "").lower()
        approves = any(t.get("confirm") == "approve" for t in s.get("turns") or [])
        assert not (sends_mail and approves), s["id"]
