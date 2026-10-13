"""Language-neutral detection of "what's open" questions.

Compares the turn's prompt embedding (the one fetch_context already computed)
with embedded EN and PT example questions. No model call per turn. The threshold
comes from `make calibrate-open-query`.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from ze_logging import get_logger

log = get_logger(__name__)

OPEN_QUERY_THRESHOLD = 0.88

OPEN_QUERY_EXAMPLES_EN: tuple[str, ...] = (
    "what do I still have open",
    "what's still pending for me",
    "what's outstanding on my side",
    "what's on my plate right now",
    "what am I still sitting with",
    "what do I still need to deal with",
    "anything I'm forgetting to do",
    "what loose ends do I have",
    "what's left on my to-do list",
    "what is still unresolved for me",
    "what am I still carrying around",
    "what is waiting on me",
    "which of my things are still unfinished",
    "what commitments do I still have open",
    "list what is still open for me",
    "show me my open items",
)

OPEN_QUERY_EXAMPLES_PT: tuple[str, ...] = (
    "o que tenho em aberto",
    "o que está pendente da minha parte",
    "o que me falta tratar",
    "o que ainda tenho para resolver",
    "tenho alguma coisa pendente",
    "o que está no meu prato neste momento",
    "o que ficou por fazer",
    "de que é que me estou a esquecer",
    "que pontas soltas tenho",
    "o que é que ainda está por resolver",
    "o que é que está à espera de mim",
    "o que ainda tenho por acabar",
    "que assuntos meus continuam em aberto",
    "com o que é que ainda ando às voltas",
    "o que é que me falta fechar",
    "tenho coisas inacabadas na minha lista",
    "o que é que deixei a meio",
    "o que é que tenho pendente com outras pessoas",
    "o que ainda me anda a pesar",
    "o que é que ainda trago em cima",
    "o que é que ainda depende de mim",
    "há alguma coisa à espera de mim",
    "lista as minhas pendências",
    "quais são as minhas pendências",
    "diz-me o que está por fazer",
    "o que é que ainda não está feito",
)

OPEN_QUERY_EXAMPLES: tuple[str, ...] = OPEN_QUERY_EXAMPLES_EN + OPEN_QUERY_EXAMPLES_PT

# E5 scores Portuguese pairs about 0.05 higher than English ones, including
# negatives such as "a vaga ainda está aberta?". Each Portuguese example's
# similarity is lowered by this much so one threshold serves both languages.
PT_SIMILARITY_OFFSET = 0.05

_DEFAULT_OFFSETS: tuple[float, ...] = (0.0,) * len(OPEN_QUERY_EXAMPLES_EN) + (
    PT_SIMILARITY_OFFSET,
) * len(OPEN_QUERY_EXAMPLES_PT)


def _unit(vectors: Any) -> np.ndarray:
    arr = np.asarray(vectors, dtype=float)
    norms = np.linalg.norm(arr, axis=-1, keepdims=True)
    return arr / np.where(norms == 0, 1.0, norms)


class OpenQueryDetector:
    def __init__(
        self,
        embedder: Any,
        *,
        examples: Sequence[str] | None = None,
        offsets: Sequence[float] | None = None,
        threshold: float = OPEN_QUERY_THRESHOLD,
    ) -> None:
        if examples is None:
            examples, offsets = OPEN_QUERY_EXAMPLES, _DEFAULT_OFFSETS
        self._embedder = embedder
        self._examples = list(examples)
        self._offsets = np.asarray(
            offsets if offsets is not None else [0.0] * len(self._examples), dtype=float
        )
        self._threshold = threshold
        self._vectors: np.ndarray | None = None

    def best_similarity(self, embedding: Any) -> float:
        if self._vectors is None:
            self._vectors = _unit(self._embedder.encode(self._examples))
        return float(np.max(self._vectors @ _unit(embedding) - self._offsets))

    def is_open_query(self, embedding: Any) -> bool:
        if embedding is None:
            return False
        try:
            return self.best_similarity(embedding) >= self._threshold
        except Exception as exc:
            log.warning("open_query_detection_failed", error=str(exc))
            return False
