"""Tests for ze_personal.social.scoring (Phase 130, User Stories 1-3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ze_personal.social.scoring import (
    filter_fresh_evidence,
    is_corroborated,
    score_evidence,
)
from ze_personal.social.types import CoOccurrenceEvidenceEvent

UTC = timezone.utc


def _event(
    *,
    source_type="email",
    is_reply_or_attendee=True,
    event_id="thread-1",
    days_ago=1,
):
    return CoOccurrenceEvidenceEvent(
        source_type=source_type,
        is_reply_or_attendee=is_reply_or_attendee,
        event_id=event_id,
        occurred_at=datetime.now(UTC) - timedelta(days=days_ago),
    )


class TestFilterFreshEvidence:
    def test_excludes_evidence_outside_30_day_window(self):
        fresh = _event(days_ago=5)
        stale = _event(event_id="thread-2", days_ago=31)

        result = filter_fresh_evidence([fresh, stale])

        assert result == [fresh]

    def test_keeps_evidence_exactly_at_boundary_excluded(self):
        # is_stale() uses `<=` for the cutoff — exactly 30 days ago counts as stale
        boundary = _event(days_ago=30)

        result = filter_fresh_evidence([boundary])

        assert result == []


class TestScoreEvidence:
    def test_reply_email_uses_email_tier_weight(self):
        event = _event(source_type="email", is_reply_or_attendee=True)
        assert score_evidence([event]) == 0.7

    def test_calendar_attendee_uses_calendar_tier_weight(self):
        event = _event(source_type="calendar", is_reply_or_attendee=True)
        assert score_evidence([event]) == 0.6

    def test_cc_only_mention_uses_research_tier_regardless_of_source(self):
        cc_email = _event(source_type="email", is_reply_or_attendee=False)
        cc_calendar = _event(
            source_type="calendar", is_reply_or_attendee=False, event_id="ev-2"
        )

        assert score_evidence([cc_email]) == 0.2
        assert score_evidence([cc_calendar]) == 0.2

    def test_conversation_reply_uses_full_weight(self):
        event = _event(source_type="conversation", is_reply_or_attendee=True)
        assert score_evidence([event]) == 1.0

    def test_empty_evidence_scores_zero(self):
        assert score_evidence([]) == 0.0

    def test_score_never_exceeds_one(self):
        events = [_event(source_type="conversation") for _ in range(3)]
        assert score_evidence(events) <= 1.0


class TestIsCorroborated:
    def test_single_event_never_corroborates(self):
        events = [_event(event_id="thread-1", days_ago=1)]
        assert is_corroborated(events) is False

    def test_two_events_same_thread_same_day_does_not_corroborate(self):
        events = [
            _event(event_id="thread-1", days_ago=1),
            _event(event_id="thread-1", days_ago=1),
        ]
        assert is_corroborated(events) is False

    def test_two_distinct_events_same_day_does_not_corroborate(self):
        events = [
            _event(event_id="thread-1", days_ago=1),
            _event(event_id="thread-2", days_ago=1),
        ]
        assert is_corroborated(events) is False

    def test_two_distinct_events_distinct_days_corroborates(self):
        events = [
            _event(event_id="thread-1", days_ago=10),
            _event(event_id="thread-2", days_ago=3),
        ]
        assert is_corroborated(events) is True

    def test_cc_only_broadcast_single_event_never_corroborates(self):
        # A single CC-heavy broadcast is one event on one day — corroboration
        # requires distinct events across distinct days, independent of the
        # weak research-tier weight (SC-003).
        events = [
            _event(
                source_type="email",
                is_reply_or_attendee=False,
                event_id="broadcast-1",
                days_ago=2,
            )
        ]
        assert is_corroborated(events) is False
