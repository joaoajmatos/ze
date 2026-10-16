from __future__ import annotations

import numpy as np
import pytest

from ze_priority.open_query import OpenQueryDetector

_EXAMPLES = ("whats open", "o que esta pendente")
_VECS = {
    "whats open": np.array([1.0, 0.0, 0.0]),
    "o que esta pendente": np.array([0.0, 1.0, 0.0]),
}


class _Embedder:
    def __init__(self) -> None:
        self.calls = 0

    def encode_passage(self, texts):
        self.calls += 1
        return np.stack([_VECS[t] for t in texts])


def _detector(embedder=None, threshold=0.9):
    return OpenQueryDetector(
        embedder or _Embedder(), examples=_EXAMPLES, threshold=threshold
    )


def test_best_similarity_is_the_max_dot_product():
    d = _detector()
    assert d.best_similarity(np.array([0.6, 0.8, 0.0])) == pytest.approx(0.8)


def test_at_threshold_is_true_below_is_false():
    d = _detector(threshold=0.8)
    assert d.is_open_query(np.array([0.6, 0.8, 0.0])) is True
    assert d.is_open_query(np.array([0.5, 0.5, 0.7071])) is False


def test_embedding_is_normalised_before_comparing():
    assert _detector().is_open_query(np.array([5.0, 0.0, 0.0])) is True


def test_examples_are_embedded_once():
    embedder = _Embedder()
    d = _detector(embedder)
    for _ in range(5):
        d.is_open_query(np.array([1.0, 0.0, 0.0]))
    assert embedder.calls == 1


def test_none_embedding_is_false():
    assert _detector().is_open_query(None) is False


def test_embedder_failure_is_false_and_retried_later():
    class Flaky(_Embedder):
        def encode_passage(self, texts):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("model not loaded")
            return np.stack([_VECS[t] for t in texts])

    embedder = Flaky()
    d = _detector(embedder)
    vec = np.array([1.0, 0.0, 0.0])

    assert d.is_open_query(vec) is False
    assert d.is_open_query(vec) is True
    assert embedder.calls == 2


def test_detector_embeds_examples_as_passages():
    # The 0.88 threshold and 0.05 PT offset are calibrated passage-vs-passage
    # (eval/calibration/open_query.py); a query prefix would shift every score.
    class Strict(_Embedder):
        def encode_query(self, texts):
            raise AssertionError("open-query examples must be passage-encoded")

    embedder = Strict()
    d = _detector(embedder)

    assert d.is_open_query(np.array([1.0, 0.0, 0.0])) is True
    assert embedder.calls == 1
