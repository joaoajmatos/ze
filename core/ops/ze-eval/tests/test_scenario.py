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


def test_sandbox_scenarios_run_only_with_the_explicit_flag(monkeypatch) -> None:
    from ze_eval.scenario import SANDBOX_ENV, is_runnable

    scenario = {"id": "x", "requires_sandbox": True}
    monkeypatch.delenv(SANDBOX_ENV, raising=False)
    assert is_runnable(scenario) is False
    monkeypatch.setenv(SANDBOX_ENV, "0")
    assert is_runnable(scenario) is False
    monkeypatch.setenv(SANDBOX_ENV, "1")
    assert is_runnable(scenario) is True
    assert is_runnable({"id": "y"}) is True


def test_every_calendar_write_is_sandbox_only() -> None:
    for scenario in load_scenarios():
        tools = [
            t if isinstance(t, str) else t.get("name")
            for t in scenario.get("expected_tools") or []
        ]
        if "delete_event" in tools or "create_event" in tools:
            assert scenario.get("requires_sandbox") is True, scenario["id"]


def test_sandbox_delete_scenario_creates_then_deletes_its_own_event() -> None:
    (scenario,) = [
        s
        for s in load_scenarios(tag="confirmation")
        if s["id"] == "write_confirmation_delete_event_approve"
    ]
    assert scenario["requires_sandbox"] is True
    deletes = [t for t in scenario["expected_tools"] if t["name"] == "delete_event"]
    creates = [t for t in scenario["expected_tools"] if t["name"] == "create_event"]
    assert creates and deletes
    assert max(c["turn"] for c in creates if c.get("gate") == "approved") < min(
        d["turn"] for d in deletes if d.get("gate") == "parked"
    )


def test_companion_render_scenarios_cover_every_render_tool_and_two_negatives() -> None:
    render = [s for s in load_scenarios(tag="render") if s["file"] == "companion"]
    positive = {
        t if isinstance(t, str) else t["name"]
        for s in render
        if "negative" not in s["tags"]
        for t in s["expected_tools"]
    }
    assert {
        "render_chart",
        "render_table",
        "render_metric",
        "render_timeline",
        "render_form",
        "render_choice_group",
        "render_consent",
        "render_connect_account",
        "render_review",
        "render_connections",
    } <= positive

    negatives = [s for s in render if "negative" in s["tags"]]
    assert len(negatives) == 2
    for s in negatives:
        assert s["expected_agent"] == "companion"
        assert all(t["count"] == 0 for t in s["expected_tools"])
        assert all(t["name"].startswith("render_") for t in s["expected_tools"])
