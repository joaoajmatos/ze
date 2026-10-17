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


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def topic_words(topic: str) -> list[str]:
    return [w for w in re.findall(r"\w+", _fold(topic)) if len(w) >= _TOPIC_WORD_MIN]


def shared_words(words: list[str], text: str) -> int:
    folded = _fold(text)
    return sum(1 for word in words if word in folded)
