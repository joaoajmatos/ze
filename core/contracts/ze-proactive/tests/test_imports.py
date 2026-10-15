def test_public_api_imports() -> None:
    from ze_proactive.job import ProactiveJob, proactive_job
    from ze_proactive.notifier import ProactiveNotifier
    from ze_proactive.scheduler import ProactiveScheduler

    assert ProactiveJob is not None
    assert callable(proactive_job)
    assert ProactiveNotifier is not None
    assert ProactiveScheduler is not None


def test_governor_api_imports() -> None:
    from ze_proactive.governor import decide
    from ze_proactive.push_kinds import registered_push_kinds
    from ze_proactive.types import PushKind, PushOutcome

    assert callable(decide) and callable(registered_push_kinds)
    assert PushKind is not None and PushOutcome is not None
