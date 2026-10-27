from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from ze_proactive.bootstrap import build_notifier
from ze_proactive.push_log_store import PushLogStore


def test_build_notifier_wires_the_claim_store_and_the_shared_budget():
    settings = SimpleNamespace(
        config={"proactive": {"budget": {"max_pushes_per_day": 3}}}
    )

    notifier = build_notifier(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), settings
    )

    assert notifier.max_discretionary_per_day == 3
    assert isinstance(notifier._push_log, PushLogStore)


def test_build_notifier_defaults_the_budget_to_five():
    notifier = build_notifier(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), SimpleNamespace(config={})
    )

    assert notifier.max_discretionary_per_day == 5
