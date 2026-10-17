from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_priority.compose import rules
from ze_priority.compose.types import SourceSnapshot
from ze_worldstate.types import LoopState

from tests.factories import make_goal_progress, make_held_write, make_loop

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _suspected(**kw):
    kw.setdefault("state", LoopState.SUSPECTED)
    kw.setdefault("claim_kind", ClaimKind.SUSPICION)
    kw.setdefault("provenance", "email")
    kw.setdefault("updated_at", NOW - timedelta(hours=5))
    return make_loop(**kw)


def _gate_goal(title="Ship the report", days=3, **kw):
    return make_goal_progress(
        goal_overrides={"title": title, "status": "awaiting_gate"},
        gate_id=uuid4(),
        gate_title="Approve pricing",
        gate_open_since=NOW - timedelta(days=days),
        **kw,
    )


def _snapshot(loops=(), goals=(), held=(), failed=()):
    return SourceSnapshot(
        loops=list(loops), goals=list(goals), held_writes=list(held), failed=set(failed)
    )


def _cards(draft):
    return [c for c in draft.components if c.type == "claim_card"]


def test_us2_independent_example():
    hold = make_held_write(expires_at=NOW + timedelta(hours=20))
    goal = _gate_goal()
    s1 = _suspected(title="Call the bank", confidence=0.4)
    s2 = _suspected(title="Pay the invoice", confidence=0.8)

    draft = rules.decisions(_snapshot([s1, s2], [goal], [hold]), NOW)

    assert draft.components[0].text == "4 TO DECIDE"
    cards = _cards(draft)
    assert [c.claim.subject for c in cards] == ["held_write", "goal", "loop", "loop"]
    assert [c.title for c in cards[2:]] == ["Pay the invoice", "Call the bank"]
    assert [c.tone for c in cards] == ["cream", "cream", "dotted", "dotted"]
    assert all(c.tone != "hot" for c in cards)


def test_held_write_card_actions_and_posture():
    hold = make_held_write(
        items=[
            {"effect_phrase": "Send the email", "summary": "Invoice to Ana"},
            {"effect_phrase": "Create the event", "summary": "Lunch"},
        ],
        expires_at=NOW + timedelta(hours=20, minutes=30),
        created_at=NOW - timedelta(hours=4),
    )
    [card] = _cards(rules.decisions(_snapshot(held=[hold]), NOW))

    assert card.title == "Send the email: Invoice to Ana (+1 more)"
    assert card.claim.kind is None
    assert card.claim.subject == "held_write"
    assert card.claim.ref_id == hold.request_id
    assert card.claim.state == "open"
    assert card.claim.confidence is None
    assert card.claim.as_of == hold.created_at.isoformat()
    assert card.lines == ["From workflow 'Weekly invoices'"]
    assert card.readouts[0].value == "expires in 20 h"
    assert [(a.label, a.intent, a.ref_id) for a in card.actions] == [
        ("Approve", "approve_held_write", hold.request_id),
        ("Deny", "deny_held_write", hold.request_id),
    ]


def test_gate_card_actions_use_gate_id_and_goal_id():
    goal = _gate_goal(days=3)
    [card] = _cards(rules.decisions(_snapshot(goals=[goal]), NOW))

    assert card.claim.state == "awaiting_gate"
    assert card.claim.ref_id == str(goal.goal.id)
    assert card.span == 8
    assert card.lines == ["Approve pricing"]
    assert card.readouts[-1].value == "waiting 3 d"
    assert [(a.label, a.intent, a.ref_id) for a in card.actions] == [
        ("Approve", "approve_gate", str(goal.gate_id)),
        ("Open", "open", str(goal.goal.id)),
    ]


def test_a_stale_gate_is_honest_about_slipping_but_never_hot():
    goal = _gate_goal(days=12, stuck_since=NOW - timedelta(days=12))
    [card] = _cards(rules.decisions(_snapshot(goals=[goal]), NOW))
    assert card.tone == "cream"
    assert card.claim.slipped is True


def test_suspicion_card_actions_and_posture():
    loop = _suspected(title="Call the bank", confidence=0.55)
    [card] = _cards(rules.decisions(_snapshot([loop]), NOW))

    assert card.claim.kind == "suspicion"
    assert card.claim.state == "suspected"
    assert card.lines == ["Seen in your email"]
    assert card.readouts[0].value == "0.55"
    assert [(a.label, a.intent, a.ref_id) for a in card.actions] == [
        ("Yes, track it", "confirm_loop", str(loop.id)),
        ("Drop", "drop_loop", str(loop.id)),
    ]


def test_active_and_drifting_loops_are_not_decisions():
    loops = [
        make_loop(state=LoopState.ACTIVE),
        make_loop(state=LoopState.DRIFTING),
    ]
    draft = rules.decisions(_snapshot(loops), NOW)
    assert draft.components[0].text == "NOTHING TO DECIDE"
    assert _cards(draft) == []
    assert "nothing" in draft.summary.lower()


def test_expired_held_write_is_absent():
    expired = make_held_write(expires_at=NOW - timedelta(minutes=1))
    draft = rules.decisions(_snapshot(held=[expired]), NOW)
    assert _cards(draft) == []


def test_order_within_kind():
    soon = make_held_write(expires_at=NOW + timedelta(hours=2))
    later = make_held_write(expires_at=NOW + timedelta(hours=9))
    old_gate = _gate_goal("Old gate", days=9)
    new_gate = _gate_goal("New gate", days=1)

    cards = _cards(
        rules.decisions(_snapshot(goals=[new_gate, old_gate], held=[later, soon]), NOW)
    )

    assert [c.claim.ref_id for c in cards[:2]] == [soon.request_id, later.request_id]
    assert [c.title for c in cards[2:]] == ["Old gate", "New gate"]


def test_cap_six_per_kind():
    holds = [make_held_write(expires_at=NOW + timedelta(hours=i + 1)) for i in range(9)]
    draft = rules.decisions(_snapshot(held=holds), NOW)
    assert len(_cards(draft)) == 6
    assert draft.components[0].text == "9 TO DECIDE"


def test_summary_and_sources_failed():
    hold = make_held_write()
    draft = rules.decisions(_snapshot(held=[hold], failed={"goals"}), NOW)
    assert draft.sources_failed == ["goals"]
    assert "1 held write" in draft.summary
    assert "goals" in draft.summary


def test_every_source_failed_reads_could_not_read():
    draft = rules.decisions(_snapshot(failed={"loops", "goals", "held_writes"}), NOW)
    assert draft.components[0].text == "COULD NOT READ THE WORLD"
    assert len(draft.components) == 1


def test_provenance_keys_are_worded_not_shown_raw():
    loop = _suspected(provenance="user_declared")
    [card] = _cards(rules.decisions(_snapshot([loop]), NOW))
    assert card.lines == ["Seen in what you told me"]
    odd = _suspected(provenance="plugin_thing")
    [card] = _cards(rules.decisions(_snapshot([odd]), NOW))
    assert card.lines == ["Seen in plugin thing"]
