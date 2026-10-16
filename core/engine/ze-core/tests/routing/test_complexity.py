import pytest

from ze_core.routing.complexity import ComplexityEstimator


@pytest.fixture
def estimator():
    return ComplexityEstimator()


class TestWordCount:
    def test_long_prompt_scores_complex(self, estimator):
        prompt = " ".join(["word"] * 35)
        assert estimator.classify(prompt, "research", 0.9) == "complex"

    def test_very_short_prompt_scores_simple(self, estimator):
        # <12 words, "what is" simple keyword, high confidence → well below -1
        assert estimator.classify("what is this", "research", 0.9) == "simple"


class TestCompanionBonus:
    def test_companion_biases_complex(self, estimator):
        # 7 words (-1), companion (+2), high confidence (-1) → score 0 → complex
        prompt = "tell me the weather today, would you"
        assert estimator.classify(prompt, "companion", 0.9) == "complex"
        assert estimator.classify(prompt, "research", 0.9) == "simple"


class TestKeywords:
    def test_complex_keywords_score_complex(self, estimator):
        assert (
            estimator.classify(
                "analyze and compare these two approaches", "research", 0.5
            )
            == "complex"
        )

    def test_simple_keywords_score_simple(self, estimator):
        assert (
            estimator.classify("what is the definition of recursion", "research", 0.9)
            == "simple"
        )


class TestConfidence:
    def test_high_confidence_nudges_toward_simple(self, estimator):
        # 8 words, high confidence: score = -1 - 1 = -2 → simple
        assert (
            estimator.classify("tell me the weather today", "research", 0.9) == "simple"
        )


class TestBoundary:
    def test_score_minus_one_is_complex(self, estimator):
        # 10 words, no special keywords, confidence 0.5 → score 0 → complex
        prompt = "can you help me with something I need done now"
        assert estimator.classify(prompt, "research", 0.5) == "complex"
