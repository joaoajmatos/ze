from __future__ import annotations

import re
import unicodedata

import numpy as np

MATCH_FLOOR = 0.55


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0

# Real E5 passage cosines for unrelated short texts sit at 0.81-0.87 (measured
# 2026-10-17), so MATCH_FLOOR cannot tell a topic from noise. A topic matches when it
# shares a word with the text or is nearly identical to it.
TOPIC_FLOOR = 0.90
_TOPIC_WORD_MIN = 4
_STEM_MIN = 5
_STEM_LEN = 5
_TOKEN = re.compile(r"\w+")
_STOPWORDS = frozenset(
    """
    about after also been before doing from going have into just more most much only over than that
    their them then there these they this those very what when where which while will
    with would your
    para como com uma uns umas dos das nos nas pelo pela pelos pelas seu sua seus suas
    isso isto esse essa esses essas este esta estes estas aquele aquela mais muito
    entre sobre depois antes quando onde qual quais tambem ainda sempre ate
    """.split()
)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(_fold(text))


def topic_words(topic: str) -> list[str]:
    return [
        w
        for w in _tokens(topic)
        if len(w) >= _TOPIC_WORD_MIN and w not in _STOPWORDS
    ]


def shared_words(words: list[str], text: str) -> int:
    """Topic words that appear as whole words in the text, or share a 5-letter stem."""
    tokens = set(_tokens(text))
    stems = {t[:_STEM_LEN] for t in tokens if len(t) >= _STEM_MIN}
    return sum(
        1
        for word in words
        if word in tokens or (len(word) >= _STEM_MIN and word[:_STEM_LEN] in stems)
    )
