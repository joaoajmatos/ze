from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import numpy as np
import pytest
from structlog.testing import capture_logs
from ze_proactive.candidates import BarThresholds, PushCandidate
from ze_proactive.types import OncePer

from ze_priority.push_bar import PushBar

THRESHOLDS = BarThresholds(
    confidence=0.5,
    relevance=0.5,
    novelty_similarity_max=0.9,
    grounding=0.5,
    inline_cooldown_hours=24.0,
)


class FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]] | None = None) -> None:
        self._vectors = vectors or {}

    def encode_passage(self, text: str) -> np.ndarray:
        return np.array(self._vectors.get(text, [1.0, 0.0]), dtype=float)


class FakeNLI:
    def __init__(self, grounded: float = 1.0, *, raises: bool = False) -> None:
        self._grounded = grounded
        self._raises = raises
        self.score_calls = 0

    async def scores(self, pairs):
        self.score_calls += 1
        if self._raises:
            raise RuntimeError("nli down")
        return [{"entailment": 1.0} for _ in pairs]

    def grounding_score(self, hypothesis, evidence_texts, scores=None):
        return self._grounded

    def pair_is_scorable(self, premise, hypothesis):
        return True


class FakeHistory:
    def __init__(self, bodies: list[str] | None = None, *, raises: bool = False) -> None:
        self._bodies = bodies or []
        self._raises = raises
        self.calls: list[float] = []

    async def recent_discretionary_bodies(self, hours: float) -> list[str]:
        self.calls.append(hours)
        if self._raises:
            raise RuntimeError("history down")
        return list(self._bodies)


class FakeMentions:
    def __init__(self, mentioned: bool = False, *, raises: bool = False) -> None:
        self._mentioned = mentioned
        self._raises = raises
        self.calls: list[tuple[str, object, float]] = []

    async def mentioned_inline_within(self, source_kind, source_id, hours) -> bool:
        self.calls.append((source_kind, source_id, hours))
        if self._raises:
            raise RuntimeError("mentions down")
        return self._mentioned


class Counter:
    """A thunk that counts calls."""

    def __init__(self, value, *, raises: bool = False) -> None:
        self.value = value
        self.raises = raises
        self.calls = 0

    async def __call__(self):
        self.calls += 1
        if self.raises:
            raise RuntimeError("thunk failed")
        return self.value


def _candidate(
    *,
    kind: str = "loop",
    body: str = "body",
    confidence: float = 0.9,
    relevance: Counter | None = None,
    labels: Counter | None = None,
) -> PushCandidate:
    source_id = uuid4()
    return PushCandidate(
        source_kind=kind,
        source_id=source_id,
        entity=object(),
        body=body,
        claim="claim",
        confidence=confidence,
        relevance=relevance or Counter(0.9),
        evidence_labels=labels or Counter(("evidence",)),
        once_per=OncePer(f"{kind}:{source_id}", within=timedelta(days=7)),
    )


def _bar(
    *,
    embedder=None,
    nli="default",
    history=None,
    mentions=None,
) -> PushBar:
    return PushBar(
        embedder=embedder if embedder is not None else FakeEmbedder(),
        nli=FakeNLI() if nli == "default" else nli,
        history=history or FakeHistory(),
        mentions=mentions or FakeMentions(),
    )


async def _only(bar: PushBar, candidate: PushCandidate, thresholds=THRESHOLDS):
    (verdict,) = await bar.screen([candidate], thresholds)
    return verdict


async def test_candidate_passing_everything_passes():
    verdict = await _only(_bar(), _candidate())
    assert verdict.passed is True
    assert verdict.reason is None


async def test_empty_input_reads_no_history():
    history = FakeHistory()
    assert await _bar(history=history).screen([], THRESHOLDS) == []
    assert history.calls == []


async def test_low_confidence():
    verdict = await _only(_bar(), _candidate(confidence=0.4))
    assert (verdict.passed, verdict.reason) == (False, "low_confidence")


async def test_irrelevant():
    verdict = await _only(_bar(), _candidate(relevance=Counter(0.1)))
    assert (verdict.passed, verdict.reason) == (False, "irrelevant")


async def test_mentioned_recently():
    verdict = await _only(
        _bar(mentions=FakeMentions(mentioned=True)), _candidate()
    )
    assert (verdict.passed, verdict.reason) == (False, "mentioned_recently")


async def test_not_novel():
    embedder = FakeEmbedder({"old": [1.0, 0.0], "body": [1.0, 0.01]})
    verdict = await _only(
        _bar(embedder=embedder, history=FakeHistory(["old"])), _candidate()
    )
    assert (verdict.passed, verdict.reason) == (False, "not_novel")


async def test_novel_when_history_differs():
    embedder = FakeEmbedder({"old": [0.0, 1.0], "body": [1.0, 0.0]})
    verdict = await _only(
        _bar(embedder=embedder, history=FakeHistory(["old"])), _candidate()
    )
    assert verdict.passed is True


async def test_ungrounded():
    verdict = await _only(_bar(nli=FakeNLI(grounded=0.1)), _candidate())
    assert (verdict.passed, verdict.reason) == (False, "ungrounded")


async def test_first_failing_condition_names_the_reason():
    embedder = FakeEmbedder({"old": [1.0, 0.0], "body": [1.0, 0.0]})
    bar = _bar(
        embedder=embedder,
        history=FakeHistory(["old"]),
        mentions=FakeMentions(mentioned=True),
        nli=FakeNLI(grounded=0.0),
    )
    # fails mention, novelty and grounding: the earliest wins
    assert (await _only(bar, _candidate())).reason == "mentioned_recently"
    # fails confidence and relevance: confidence wins
    low = _candidate(confidence=0.1, relevance=Counter(0.0))
    assert (await _only(bar, low)).reason == "low_confidence"
    # fails relevance, mention, novelty and grounding: relevance wins
    assert (await _only(bar, _candidate(relevance=Counter(0.0)))).reason == "irrelevant"


async def test_confidence_failure_calls_no_thunk():
    relevance, labels = Counter(0.9), Counter(("e",))
    await _only(_bar(), _candidate(confidence=0.1, relevance=relevance, labels=labels))
    assert (relevance.calls, labels.calls) == (0, 0)


async def test_evidence_labels_called_only_at_grounding_step():
    relevance, labels = Counter(0.9), Counter(("e",))
    mentions = FakeMentions(mentioned=True)
    await _only(_bar(mentions=mentions), _candidate(relevance=relevance, labels=labels))
    assert (relevance.calls, labels.calls) == (1, 0)

    await _only(_bar(), _candidate(relevance=relevance, labels=labels))
    assert (relevance.calls, labels.calls) == (2, 1)


async def test_relevance_exception_rejects_as_irrelevant():
    with capture_logs() as logs:
        verdict = await _only(
            _bar(), _candidate(relevance=Counter(0.9, raises=True))
        )
    assert (verdict.passed, verdict.reason) == (False, "irrelevant")
    assert any(e["event"] == "push_bar_relevance_check_failed" for e in logs)


async def test_inline_cooldown_none_skips_mention_check():
    mentions = FakeMentions(mentioned=True)
    thresholds = BarThresholds(0.5, 0.5, 0.9, 0.5, None)
    verdict = await _only(_bar(mentions=mentions), _candidate(), thresholds)
    assert verdict.passed is True
    assert mentions.calls == []


async def test_mention_check_gets_kind_id_and_hours():
    mentions = FakeMentions()
    candidate = _candidate(kind="loop")
    await _only(_bar(mentions=mentions), candidate)
    assert mentions.calls == [("loop", candidate.source_id, 24.0)]


async def test_empty_evidence_skips_grounding():
    nli = FakeNLI(grounded=0.0)
    verdict = await _only(_bar(nli=nli), _candidate(labels=Counter(())))
    assert verdict.passed is True
    assert nli.score_calls == 0


async def test_mention_exception_passes_and_logs():
    with capture_logs() as logs:
        verdict = await _only(
            _bar(mentions=FakeMentions(raises=True)), _candidate()
        )
    assert verdict.passed is True
    assert any(e["event"] == "push_bar_mention_check_failed" for e in logs)


async def test_novelty_exception_passes_and_logs():
    with capture_logs() as logs:
        verdict = await _only(
            _bar(history=FakeHistory(["old"], raises=True)), _candidate()
        )
    assert verdict.passed is True
    assert any(e["event"] == "push_bar_novelty_check_failed" for e in logs)


async def test_grounding_exception_passes_and_logs():
    with capture_logs() as logs:
        verdict = await _only(_bar(nli=FakeNLI(raises=True)), _candidate())
    assert verdict.passed is True
    assert any(e["event"] == "push_bar_grounding_check_failed" for e in logs)


async def test_evidence_labels_exception_passes_and_logs():
    with capture_logs() as logs:
        verdict = await _only(
            _bar(), _candidate(labels=Counter((), raises=True))
        )
    assert verdict.passed is True
    assert any(e["event"] == "push_bar_grounding_check_failed" for e in logs)


async def test_history_read_once_for_three_candidates():
    history = FakeHistory(["old"])
    bar = _bar(history=history)
    verdicts = await bar.screen([_candidate(), _candidate(), _candidate()], THRESHOLDS)
    assert len(verdicts) == 3
    assert history.calls == [48.0]


async def test_verdicts_keep_input_order():
    first, second = _candidate(confidence=0.1), _candidate()
    verdicts = await _bar().screen([first, second], THRESHOLDS)
    assert [v.candidate for v in verdicts] == [first, second]
    assert [v.passed for v in verdicts] == [False, True]


def test_nli_is_required():
    with pytest.raises(TypeError):
        PushBar(embedder=FakeEmbedder(), history=FakeHistory(), mentions=FakeMentions())  # type: ignore[call-arg]


async def test_nli_none_logs_once_and_skips_grounding():
    with capture_logs() as logs:
        bar = PushBar(
            embedder=FakeEmbedder(),
            nli=None,
            history=FakeHistory(),
            mentions=FakeMentions(),
        )
        labels = Counter(("e",))
        first = await _only(bar, _candidate(labels=labels))
        second = await _only(bar, _candidate(labels=labels))
    assert first.passed and second.passed
    assert labels.calls == 0
    assert [e["event"] for e in logs].count("push_bar_grounding_off") == 1


async def test_unknown_source_kind_is_screened_like_any_other():
    verdict = await _only(_bar(), _candidate(kind="test_kind"))
    assert verdict.passed is True
    low = await _only(_bar(), _candidate(kind="test_kind", confidence=0.0))
    assert low.reason == "low_confidence"
