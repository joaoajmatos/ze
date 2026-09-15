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


def test_correlation_reexports_are_the_real_classes() -> None:
    import ze_correlation.store
    import ze_correlation.types
    from ze_sdk.correlation import (
        EvidenceRef,
        Hypothesis,
        HypothesisNotFoundError,
        HypothesisStore,
        PostgresHypothesisStore,
    )

    assert Hypothesis is ze_correlation.types.Hypothesis
    assert EvidenceRef is ze_correlation.types.EvidenceRef
    assert PostgresHypothesisStore is ze_correlation.store.PostgresHypothesisStore
    assert HypothesisNotFoundError is ze_correlation.store.HypothesisNotFoundError
    assert HypothesisStore is not None
