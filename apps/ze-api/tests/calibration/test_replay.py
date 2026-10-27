"""The replay fakes are deterministic and well formed. No network."""

from __future__ import annotations

import numpy as np
from tests.calibration.replay import FakeHaiku, HashEmbedder, ReplayClient
from ze_agents.system_one import SystemOneQuestion

CRITERIA = {"alpha": "a", "beta": "b", "gamma": "c"}


def _questions() -> dict[str, SystemOneQuestion]:
    return {
        "pick": SystemOneQuestion(type="choice", instructions="?", criteria=CRITERIA),
        "level": SystemOneQuestion(type="noul", instructions="?"),
    }


async def test_same_input_gives_the_same_answer_twice():
    client = ReplayClient()
    first = await client.evaluate({"user": "hello"}, _questions())
    second = await client.evaluate({"user": "hello"}, _questions())
    assert first == second
    other = await client.evaluate({"user": "bye"}, _questions())
    assert other.answers["level"].noul != first.answers["level"].noul


async def test_choice_answers_are_among_the_criteria_keys():
    client = ReplayClient()
    for i in range(40):
        result = await client.evaluate({"user": f"row {i}"}, _questions())
        pick = result.answers["pick"]
        assert pick.choice in CRITERIA
        assert set(pick.probabilities) == set(CRITERIA)
        assert abs(sum(pick.probabilities.values()) - 1.0) < 1e-3
        assert pick.confidence == pick.probabilities[pick.choice]
        assert 0.0 <= result.answers["level"].noul <= 1.0
        assert result.model == "replay"


def test_hash_embedder_is_deterministic_and_unit_length():
    embedder = HashEmbedder()
    a = embedder.encode_passage("same", normalize_embeddings=True)
    assert np.allclose(a, embedder.encode_passage("same"))
    assert abs(float(np.linalg.norm(a)) - 1.0) < 1e-9
    batch = embedder.encode_passage(["one", "two"], normalize_embeddings=True)
    assert batch.shape[0] == 2
    assert embedder.encode_query("same").shape == a.shape


async def test_fake_haiku_replies_with_parseable_json():
    import json

    haiku = FakeHaiku()
    for i in range(10):
        raw = await haiku.complete([{"role": "user", "content": f"text {i}"}])
        body = raw.strip().removeprefix("```json").removesuffix("```").strip()
        assert set(json.loads(body)) >= {"is_loop", "title", "resolves_existing"}
