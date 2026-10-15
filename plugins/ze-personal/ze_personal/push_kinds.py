from __future__ import annotations

from ze_sdk.proactive import PushKind

MORNING_BRIEF = PushKind("morning_brief", "accountability", "normal", "personal")
INSIGHT = PushKind("insight", "discretionary", "normal", "personal")
CONTACT_REVIEW = PushKind("contact_review", "discretionary", "low", "personal")
