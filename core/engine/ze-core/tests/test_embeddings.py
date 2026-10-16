import numpy as np
import pytest

from ze_core import embeddings
from ze_core.embeddings import E5Embedder, get_embedder


class _RecordingModel:
    def __init__(self, name: str) -> None:
        self.calls: list[object] = []

    def encode(self, text, normalize_embeddings=True, **kwargs):
        self.calls.append(text)
        return np.ones(3) if isinstance(text, str) else np.ones((len(text), 3))


@pytest.fixture
def embedder(monkeypatch) -> E5Embedder:
    monkeypatch.setattr(embeddings, "SentenceTransformer", _RecordingModel)
    return E5Embedder("stub")


def test_encode_query_prefixes_query(embedder):
    embedder.encode_query("what is on my plate")
    assert embedder._model.calls == ["query: what is on my plate"]


def test_encode_passage_prefixes_passage(embedder):
    embedder.encode_passage("lives in Porto")
    assert embedder._model.calls == ["passage: lives in Porto"]


def test_encode_passage_batches_with_prefix(embedder):
    vecs = embedder.encode_passage(["a", "b"])
    assert embedder._model.calls == [["passage: a", "passage: b"]]
    assert vecs.shape == (2, 3)


def test_there_is_no_unprefixed_encode(embedder):
    assert not hasattr(embedder, "encode")


@pytest.fixture
def clear_embedder_cache():
    get_embedder.cache_clear()
    yield
    get_embedder.cache_clear()


@pytest.mark.slow
def test_real_model_vectors_are_768_dim_and_normalised(clear_embedder_cache):
    embedder = get_embedder()
    vec = embedder.encode_passage("hello world")
    assert vec.shape == (768,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-5


@pytest.mark.slow
def test_real_model_query_and_passage_differ(clear_embedder_cache):
    embedder = get_embedder()
    query = embedder.encode_query("where do I live?")
    passage = embedder.encode_passage("where do I live?")
    assert float(np.dot(query, passage)) < 0.999


@pytest.mark.slow
def test_real_model_is_singleton(clear_embedder_cache):
    assert get_embedder() is get_embedder()
