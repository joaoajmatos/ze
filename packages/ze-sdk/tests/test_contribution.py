def test_contribution_reexports_are_identical_to_ze_plugin_originals() -> None:
    import ze_plugin.contribution as _plugin
    import ze_sdk.contribution as _sdk

    for name in (
        "Contribution",
        "EvidenceRef",
        "SourceFunction",
        "TargetFace",
        "validate_and_submit",
    ):
        assert getattr(_sdk, name) is getattr(_plugin, name)


def test_submit_and_detect_collisions_reexport_is_identical_to_ze_collision_original() -> (
    None
):
    import ze_collision.detect as _collision
    import ze_sdk.contribution as _sdk

    assert _sdk.submit_and_detect_collisions is _collision.submit_and_detect_collisions


def test_perception_fact_helpers_reexport_from_ze_memory() -> None:
    import ze_memory.contribution as _memory
    import ze_sdk.memory as _sdk

    assert _sdk.submit_perception_facts is _memory.submit_perception_facts
    assert _sdk.fact_to_contribution is _memory.fact_to_contribution
    assert _sdk.PerceptionFactSubmit is _memory.PerceptionFactSubmit


def test_action_record_helpers_reexport_from_ze_memory() -> None:
    import ze_memory.action_records as _memory
    import ze_sdk.contribution as _sdk

    assert _sdk.submit_action_record is _memory.submit_action_record
    assert _sdk.ActionRecordDraft is _memory.ActionRecordDraft
    assert not hasattr(_sdk, "PostgresActionRecordStore")


def test_feedback_record_helpers_reexport_from_ze_memory() -> None:
    import ze_memory.feedback_records as _memory
    import ze_sdk.contribution as _sdk

    assert _sdk.submit_feedback_record is _memory.submit_feedback_record
    assert _sdk.FeedbackRecordDraft is _memory.FeedbackRecordDraft
    assert _sdk.FeedbackKind is _memory.FeedbackKind
    assert _sdk.FeedbackStore is _memory.FeedbackStore
    assert not hasattr(_sdk, "PostgresFeedbackStore")


def test_tool_reversibility_reexport() -> None:
    import ze_agents.reversibility as _agents
    import ze_sdk

    assert ze_sdk.ToolReversibility is _agents.ToolReversibility
