from __future__ import annotations

import pytest

from ze_proactive.governor import decide
from ze_proactive.types import PushKind

REQ = PushKind("g_req", "requested", "high", "tests")
ACC = PushKind("g_acc", "accountability", "normal", "tests")
DIS = PushKind("g_dis", "discretionary", "normal", "tests")


@pytest.mark.parametrize(
    "kind,quiet,budget,expected",
    [
        (REQ, False, None, "deliver"),
        (REQ, True, None, "deliver"),
        (ACC, False, None, "deliver"),
        (ACC, True, None, "hold"),
        (DIS, False, True, "deliver"),
        (DIS, False, False, "suppress"),
        (DIS, True, True, "hold"),
        (DIS, True, False, "hold"),
    ],
)
def test_decide(kind, quiet, budget, expected):
    assert decide(kind, quiet_now=quiet, budget_won=budget) == expected
