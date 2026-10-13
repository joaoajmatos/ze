from __future__ import annotations

from ze_sdk.proactive import PushKind

FINANCE_STALE_NUDGE = PushKind("finance_stale_nudge", "discretionary", "low", "finance")
FINANCE_RECURRING_NEW = PushKind("finance_recurring_new", "discretionary", "normal", "finance")
FINANCE_PRICE_CHANGE = PushKind("finance_price_change", "discretionary", "normal", "finance")
