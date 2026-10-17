def test_public_api_imports() -> None:
    from ze_sdk import BaseAgent, DataDomain, ZePlugin, agent, get_logger, tool
    from ze_sdk.channels import Channel
    from ze_sdk.memory import MemoryStore, PostgresMemoryStore
    from ze_sdk.proactive import ProactiveJob, ProactiveScheduler

    assert ZePlugin is not None
    assert DataDomain is not None
    assert callable(agent)
    assert callable(tool)
    assert callable(get_logger)
    assert BaseAgent is not None
    assert Channel is not None
    assert MemoryStore is not None
    assert PostgresMemoryStore is not None
    assert ProactiveJob is not None
    assert ProactiveScheduler is not None


def test_system_one_client_reexport():
    from ze_agents.system_one import SystemOneClient as AgentsSystemOneClient
    from ze_sdk import SystemOneClient

    assert SystemOneClient is AgentsSystemOneClient
    assert SystemOneClient.__module__ == "ze_agents.system_one"


def test_correlation_reexports_are_the_real_classes() -> None:
    import ze_correlation.store
    import ze_correlation.types
    from ze_sdk.correlation import (
        HypothesisEvidence,
        Hypothesis,
        HypothesisNotFoundError,
        HypothesisStore,
        PostgresHypothesisStore,
    )

    assert Hypothesis is ze_correlation.types.Hypothesis
    assert HypothesisEvidence is ze_correlation.types.HypothesisEvidence
    assert PostgresHypothesisStore is ze_correlation.store.PostgresHypothesisStore
    assert HypothesisNotFoundError is ze_correlation.store.HypothesisNotFoundError
    assert HypothesisStore is not None


def test_undo_payload_reexport():
    import ze_agents.tool
    import ze_sdk
    from ze_sdk import undo_payload

    assert undo_payload is ze_agents.tool.undo_payload
    assert "undo_payload" in ze_sdk.__all__
    assert undo_payload(reminder_id="r1") == {"reminder_id": "r1"}


def test_honesty_reexports_are_the_real_helpers():
    import ze_agents.honesty
    import ze_sdk

    assert ze_sdk.hold_token_sink is ze_agents.honesty.hold_token_sink
    assert ze_sdk.publish_honest_reply is ze_agents.honesty.publish_honest_reply
    assert {"hold_token_sink", "publish_honest_reply"} <= set(ze_sdk.__all__)


def test_screen_reexports_are_the_real_types() -> None:
    import ze_agents.screen
    from ze_sdk import screen

    for name in screen.__all__:
        assert getattr(screen, name) is getattr(ze_agents.screen, name)
    assert {"ScreenContext", "ScreenResolver", "ScreenLine", "ScreenRef"} <= set(screen.__all__)
