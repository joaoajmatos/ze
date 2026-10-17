from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import numpy as np
from ze_automation.workflow.types import (
    StepResult,
    Workflow,
    WorkflowExecution,
    WorkflowStep,
)
from ze_priority.compose import rules
from ze_priority.compose.types import SourceSnapshot, WorkflowDigest
from ze_priority.scoring import score_hypothesis, sort_and_rank
from ze_priority.types import PriorityRanking
from ze_worldstate.types import LoopState

from tests.factories import make_goal_progress, make_hypothesis, make_loop

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
VOCAB = ["ledgerlite", "launch", "billing", "passport", "migration"]


class FakeEmbedder:
    """Word-presence vectors over a fixed vocabulary; dict-keyed so order never matters."""

    def encode_passage(self, text: str) -> np.ndarray:
        lowered = text.lower()
        return np.array([1.0 if word in lowered else 0.0 for word in VOCAB])


def _workflow(name="LedgerLite launch checklist", enabled=True, **kw) -> Workflow:
    base = dict(
        id=uuid4(),
        name=name,
        description="Run through the launch tasks",
        steps=[WorkflowStep(task="Check")],
        schedule="0 9 * * 1",
        enabled=enabled,
        last_run_at=NOW - timedelta(hours=5),
        next_run_at=NOW + timedelta(hours=19),
        created_at=NOW - timedelta(days=30),
        updated_at=NOW - timedelta(days=1),
    )
    base.update(kw)
    return Workflow(**base)


def _execution(status="completed", error=None, results=()) -> WorkflowExecution:
    return WorkflowExecution(
        id=uuid4(),
        workflow_id=uuid4(),
        status=status,
        step_results=list(results),
        steps_snapshot=[WorkflowStep(task="Check")],
        error=error,
    )


def _snapshot(loops=(), goals=(), workflows=(), hypotheses=(), failed=()):
    ranking = PriorityRanking(
        items=sort_and_rank([score_hypothesis(h) for h in hypotheses]),
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=NOW,
    )
    return SourceSnapshot(
        ranking=ranking,
        loops=list(loops),
        goals=list(goals),
        workflows=list(workflows),
        failed=set(failed),
    )


def _topic(snapshot, topic="ledgerlite launch", embedder=FakeEmbedder()):
    return rules.topic(snapshot, topic, embedder, NOW)


def _cards(draft):
    return [c for c in draft.components if c.type == "claim_card"]


def test_us3_independent_example_floor_and_order():
    loop_hit = make_loop(title="LedgerLite launch announcement", state=LoopState.ACTIVE)
    loop_miss = make_loop(title="Renew passport", state=LoopState.ACTIVE)
    goal_hit = make_goal_progress(
        goal_overrides={"title": "Ship LedgerLite", "objective": "launch"}
    )
    goal_miss = make_goal_progress(
        goal_overrides={"title": "Passport", "objective": "renew"}
    )
    wf = WorkflowDigest(_workflow(), _execution())
    hyp = make_hypothesis(summary="LedgerLite launch overlaps billing migration")
    hyp_miss = make_hypothesis(summary="Passport and billing")

    draft = _topic(
        _snapshot([loop_miss, loop_hit], [goal_miss, goal_hit], [wf], [hyp_miss, hyp])
    )

    cards = _cards(draft)
    assert [c.claim.subject for c in cards] == [
        "loop",
        "goal",
        "workflow",
        "hypothesis",
    ]
    assert cards[0].title == "LedgerLite launch announcement"
    assert cards[1].title == "Ship LedgerLite"
    assert cards[3].claim.ref_id == str(
        next(i for i in _snapshot(hypotheses=[hyp]).ranking.items).source_id
    )


def test_goal_matches_on_objective_too():
    goal = make_goal_progress(
        goal_overrides={"title": "Q4 plan", "objective": "LedgerLite launch"}
    )
    assert [c.title for c in _cards(_topic(_snapshot(goals=[goal])))] == ["Q4 plan"]


def test_loops_are_ordered_by_similarity_then_capped_at_six():
    loops = [
        make_loop(
            title=f"LedgerLite launch billing migration {i}", state=LoopState.ACTIVE
        )
        for i in range(9)
    ]
    best = make_loop(title="LedgerLite launch", state=LoopState.ACTIVE)
    draft = _topic(_snapshot(loops + [best]))
    cards = _cards(draft)
    assert len(cards) == 6
    assert cards[0].title == "LedgerLite launch"


def test_workflow_states():
    ok = WorkflowDigest(_workflow("LedgerLite launch ok"), _execution("completed"))
    failed = WorkflowDigest(
        _workflow("LedgerLite launch failed"),
        _execution(
            "failed",
            results=[
                StepResult(
                    0, "Check the inbox", "", False, "timed out", 5, attempt_count=2
                )
            ],
        ),
    )
    never = WorkflowDigest(_workflow("LedgerLite launch never", last_run_at=None), None)
    off = WorkflowDigest(
        _workflow("LedgerLite launch off", enabled=False), _execution()
    )

    cards = {
        c.title: c
        for c in _cards(_topic(_snapshot(workflows=[ok, failed, never, off])))
    }

    assert cards["LedgerLite launch ok"].claim.state == "ok"
    assert cards["LedgerLite launch ok"].claim.slipped is False
    bad = cards["LedgerLite launch failed"]
    assert bad.claim.state == "failed" and bad.claim.slipped is True
    assert bad.lines == [
        "Step 1 of 1, “Check the inbox”, failed: it ran out of time after 2 attempts."
    ]
    assert bad.tone == "hot"
    assert cards["LedgerLite launch never"].claim.state == "never_run"
    assert cards["LedgerLite launch off"].claim.state == "off"
    assert all(
        c.claim.kind is None and c.claim.subject == "workflow" for c in cards.values()
    )
    assert cards["LedgerLite launch ok"].readouts[0].value == "5 h ago"


def test_hypothesis_card_is_dotted_with_its_kind():
    from ze_agents.claims import ClaimKind

    hyp = make_hypothesis(
        summary="LedgerLite launch overlaps billing", claim_kind=ClaimKind.SUSPICION
    )
    [card] = _cards(_topic(_snapshot(hypotheses=[hyp])))
    assert card.claim.kind == "suspicion"
    assert card.claim.subject == "hypothesis"
    assert card.claim.state == "open"
    assert card.tone == "dotted"


def test_headline_counts_slipped_and_workflows():
    drifting = make_loop(title="LedgerLite launch reply", state=LoopState.DRIFTING)
    wf = WorkflowDigest(_workflow(), _execution("failed", error="boom"))
    draft = _topic(_snapshot([drifting], workflows=[wf]))
    assert draft.components[0].text == "LEDGERLITE LAU · 2 SLIPPED · 1 WORKFLOWS"


def test_headline_topic_is_truncated_so_the_whole_line_fits_forty():
    topic = "ledgerlite launch " + "x" * 80
    drifting = make_loop(title="LedgerLite launch reply", state=LoopState.DRIFTING)
    draft = _topic(_snapshot([drifting]), topic=topic)
    text = draft.components[0].text
    assert len(text) <= 40
    assert text.endswith("· 1 SLIPPED · 0 WORKFLOWS")


def test_nothing_matching():
    unrelated = make_loop(title="Renew passport", state=LoopState.ACTIVE)
    draft = _topic(_snapshot([unrelated]), topic="billing migration?!")
    assert draft.components == [draft.components[0]]
    assert draft.components[0].text == "NOTHING ON BILLING MIGRATION"
    assert "nothing open" in draft.summary.lower()


def test_no_embedder_returns_an_empty_composition():
    draft = _topic(_snapshot([make_loop(title="LedgerLite launch")]), embedder=None)
    assert len(draft.components) == 1
    assert draft.summary == "I can't match topics right now."


def test_summary_names_every_card_and_failed_workflow_line():
    wf = WorkflowDigest(_workflow(), _execution("failed", error="timed out"))
    draft = _topic(_snapshot(workflows=[wf]))
    assert "workflow: LedgerLite launch checklist" in draft.summary
    assert "failed" in draft.summary
    assert len(draft.summary) <= 800


def test_match_workflows_filters_and_caps():
    flows = [_workflow(f"LedgerLite launch {i}") for i in range(9)] + [
        _workflow("Passport")
    ]
    matched = rules.match_workflows(flows, "ledgerlite launch", FakeEmbedder())
    assert len(matched) == 6
    assert all("LedgerLite" in w.name for w in matched)
    assert rules.match_workflows(flows, "ledgerlite", None) == []
