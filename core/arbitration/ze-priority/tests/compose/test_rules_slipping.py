from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ze_priority.compose import rules
from ze_priority.compose.types import SourceSnapshot
from ze_priority.scoring import score_relationship_staleness, sort_and_rank
from ze_priority.types import PriorityRanking, RelationshipSignal
from ze_worldstate.types import LoopState

from tests.factories import make_goal_progress, make_loop

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _loop(**kw):
    kw.setdefault("confidence", 0.7)
    kw.setdefault("updated_at", NOW - timedelta(days=1))
    return make_loop(**kw)


def _snapshot(loops=(), goals=(), persons=(), failed=()):
    ranking = PriorityRanking(
        items=sort_and_rank(
            [score_relationship_staleness(p, now=NOW) for p in persons]
        ),
        sources_succeeded={"loop", "goal", "hypothesis", "relationship"},
        sources_failed=set(),
        generated_at=NOW,
    )
    return SourceSnapshot(
        ranking=ranking,
        loops=list(loops),
        goals=list(goals),
        failed=set(failed),
    )


def _kinds(draft):
    return [c.type for c in draft.components]


def _cards(draft):
    return [c for c in draft.components if c.type == "claim_card"]


def test_us1_independent_example():
    drifting_old = _loop(
        title="Reply to Ana",
        state=LoopState.DRIFTING,
        drift_deadline=NOW - timedelta(days=4),
        drift_rationale="No reply since Tuesday.",
    )
    drifting_new = _loop(
        title="Book the dentist",
        state=LoopState.DRIFTING,
        drift_deadline=NOW - timedelta(days=1),
    )
    at_risk = _loop(
        title="Renew passport",
        state=LoopState.ACTIVE,
        drift_deadline=NOW + timedelta(days=3),
    )
    suspected = _loop(
        title="Maybe call the bank",
        state=LoopState.SUSPECTED,
    )
    stuck = make_goal_progress(
        goal_overrides={"title": "Ship the report"},
        stuck_since=NOW - timedelta(days=9),
        last_progress_at=NOW - timedelta(days=9),
    )

    draft = rules.slipping(
        _snapshot([drifting_new, at_risk, suspected, drifting_old], [stuck]), NOW
    )

    assert draft.components[0].type == "headline"
    assert draft.components[0].text == "3 SLIPPING · 1 AT RISK"
    timeline = draft.components[1]
    assert timeline.type == "claim_timeline"
    assert len(timeline.entries) == 3
    cards = _cards(draft)
    assert [c.title for c in cards] == [
        "Reply to Ana",
        "Book the dentist",
        "Ship the report",
        "Renew passport",
    ]
    assert [c.claim.slipped for c in cards] == [True, True, True, False]
    assert "Maybe call the bank" not in draft.summary
    assert all(c.claim.ref_id for c in cards)


def test_loop_card_confidence_from_is_the_stored_prior():
    loop = _loop(state=LoopState.DRIFTING, confidence=0.5, confidence_prior=0.7,
                 drift_deadline=NOW - timedelta(days=2))
    [card] = _cards(rules.slipping(_snapshot([loop]), NOW))
    assert card.claim.confidence_from == 0.7


def test_loop_card_without_a_prior_omits_confidence_from():
    loop = _loop(state=LoopState.DRIFTING, drift_deadline=NOW - timedelta(days=2))
    [card] = _cards(rules.slipping(_snapshot([loop]), NOW))
    assert card.claim.confidence_from is None


def test_loop_card_claim_comes_from_the_record():
    loop = _loop(
        state=LoopState.DRIFTING,
        confidence=0.62,
        provenance="email",
        drift_deadline=NOW - timedelta(days=2),
        drift_rationale="Nobody answered.",
    )
    [card] = _cards(rules.slipping(_snapshot([loop]), NOW))

    claim = card.claim
    assert claim.kind == "priority"
    assert claim.subject == "loop"
    assert claim.ref_id == str(loop.id)
    assert claim.confidence == 0.62
    assert claim.source == "email"
    assert claim.state == "drifting"
    assert claim.slipped is True
    assert claim.confidence_from is None
    assert claim.as_of == loop.updated_at.isoformat()
    assert card.tone == "hot"
    assert card.lines == ["Nobody answered."]
    assert card.readouts[0].value == "slipped 2 d ago"


def test_at_risk_loop_is_default_tone_with_due_readout():
    loop = _loop(state=LoopState.ACTIVE, drift_deadline=NOW + timedelta(days=3))
    [card] = _cards(rules.slipping(_snapshot([loop]), NOW))
    assert card.tone == "default"
    assert card.claim.slipped is False
    assert card.readouts[0].value == "due in 3 d"


def test_stuck_goal_card_has_progress_and_waiting_readout():
    gate_goal = make_goal_progress(
        goal_overrides={"status": "awaiting_gate"},
        gate_id=uuid4(),
        gate_title="Approve pricing",
        gate_open_since=NOW - timedelta(days=8),
        stuck_since=NOW - timedelta(days=8),
    )
    idle_goal = make_goal_progress(
        stuck_since=NOW - timedelta(days=12), last_progress_at=NOW - timedelta(days=12)
    )

    cards = _cards(rules.slipping(_snapshot(goals=[gate_goal, idle_goal]), NOW))

    assert [c.claim.state for c in cards] == ["stuck", "stuck"]
    idle, gate = cards
    assert idle.claim.ref_id == str(idle_goal.goal.id)
    assert idle.claim.kind == "priority" and idle.claim.subject == "goal"
    assert (idle.progress_done, idle.progress_total) == (2, 5)
    assert idle.readouts[-1].value == "no progress for 12 d"
    assert gate.readouts[-1].value == "waiting on you for 8 d"
    assert idle.lines == ["Next: Draft outline"]


def test_goal_without_stuck_since_is_not_listed():
    draft = rules.slipping(_snapshot(goals=[make_goal_progress()]), NOW)
    assert _cards(draft) == []
    assert draft.components[0].text == "NOTHING SLIPPING"


def test_nothing_slipping_has_no_cards_and_counts_what_is_watched():
    watched = [
        _loop(state=LoopState.ACTIVE, drift_deadline=NOW + timedelta(days=30)),
        _loop(state=LoopState.ACTIVE, drift_deadline=None),
    ]
    draft = rules.slipping(_snapshot(watched), NOW)

    assert _kinds(draft) == ["headline"]
    assert draft.components[0].text == "NOTHING SLIPPING"
    assert "watching: 2 open concerns" in draft.summary


def test_caps_six_per_kind_twelve_total_two_persons():
    drifting = [
        _loop(
            title=f"Drift {i}",
            state=LoopState.DRIFTING,
            drift_deadline=NOW - timedelta(days=i + 1),
        )
        for i in range(9)
    ]
    stuck = [
        make_goal_progress(
            goal_overrides={"title": f"Goal {i}"},
            stuck_since=NOW - timedelta(days=10 + i),
            last_progress_at=NOW - timedelta(days=10 + i),
        )
        for i in range(9)
    ]
    at_risk = [
        _loop(
            title=f"Risk {i}",
            state=LoopState.ACTIVE,
            drift_deadline=NOW + timedelta(days=1 + i % 6),
        )
        for i in range(9)
    ]
    persons = [
        RelationshipSignal(name=f"Person {i}", days_ago=10 + i) for i in range(5)
    ]

    draft = rules.slipping(_snapshot(drifting + at_risk, stuck, persons), NOW)

    cards = _cards(draft)
    assert len(cards) == 12
    assert [c.title for c in cards[:6]] == [f"Drift {i}" for i in range(8, 2, -1)]
    assert [c.title for c in cards[6:]] == [f"Goal {i}" for i in range(8, 2, -1)]
    assert draft.components[0].text == "18 SLIPPING · 9 AT RISK"

    only_persons = rules.slipping(_snapshot(persons=persons), NOW)
    person_cards = [c for c in _cards(only_persons)]
    assert len(person_cards) == 2
    assert person_cards[0].claim.subject == "person"
    assert person_cards[0].claim.state == "stale"
    assert person_cards[0].lines[0].startswith("Last contact")


def test_timeline_window_orders_by_due_at_with_nulls_last():
    far = _loop(state=LoopState.ACTIVE, drift_deadline=NOW + timedelta(days=40))
    inside = _loop(
        title="Inside", state=LoopState.ACTIVE, drift_deadline=NOW + timedelta(days=6)
    )
    past_active = _loop(
        title="Just past",
        state=LoopState.ACTIVE,
        drift_deadline=NOW - timedelta(days=2),
    )
    no_deadline = _loop(title="Undated drift", state=LoopState.DRIFTING)
    dated = _loop(
        title="Dated drift",
        state=LoopState.DRIFTING,
        drift_deadline=NOW - timedelta(days=3),
    )

    draft = rules.slipping(
        _snapshot([far, inside, past_active, no_deadline, dated]), NOW
    )

    timeline = draft.components[1]
    assert [e.title for e in timeline.entries] == [
        "Dated drift",
        "Just past",
        "Inside",
        "Undated drift",
    ]
    assert (timeline.days_before, timeline.days_after) == (7, 7)


def test_sources_failed_pass_through_to_draft_and_summary():
    draft = rules.slipping(_snapshot(failed={"goals", "hypothesis"}), NOW)
    assert draft.sources_failed == ["goals", "hypothesis"]
    assert "goals" in draft.summary


def test_summary_lists_each_card_and_stays_short():
    loop = _loop(
        title="Reply to Ana",
        state=LoopState.DRIFTING,
        drift_deadline=NOW - timedelta(days=2),
    )
    risk = _loop(
        title="Renew passport",
        state=LoopState.ACTIVE,
        drift_deadline=NOW + timedelta(days=3),
    )
    stuck = make_goal_progress(
        goal_overrides={"title": "Ship the report"},
        stuck_since=NOW - timedelta(days=9),
        last_progress_at=NOW - timedelta(days=9),
    )
    draft = rules.slipping(_snapshot([loop, risk], [stuck]), NOW)

    assert "slipped: Reply to Ana (slipped 2 d ago)" in draft.summary
    assert "stuck: Ship the report (no progress for 9 d)" in draft.summary
    assert "at risk: Renew passport (due in 3 d)" in draft.summary
    assert "watching" not in draft.summary  # both loops are cards already
    assert len(draft.summary) <= 800


def test_summary_counts_only_concerns_that_are_not_cards():
    shown = _loop(state=LoopState.DRIFTING, drift_deadline=NOW - timedelta(days=1))
    quiet = [_loop(state=LoopState.ACTIVE, drift_deadline=None) for _ in range(3)]
    draft = rules.slipping(_snapshot([shown, *quiet]), NOW)
    assert "also watching: 3 other open concerns" in draft.summary
