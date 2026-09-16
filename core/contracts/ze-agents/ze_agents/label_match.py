from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

_WHITESPACE = re.compile(r"\s+")
_PREFIX = re.compile(
    r"^(forget|cancel|drop|abandon|close)\b[\s,.:;-]*",
    re.IGNORECASE,
)
_ARTICLE = re.compile(r"^(the|my|a|an)\b[\s,.:;-]*", re.IGNORECASE)


@dataclass(frozen=True)
class Unique:
    item_id: Any


@dataclass(frozen=True)
class Miss:
    pass


@dataclass(frozen=True)
class Ambiguous:
    item_ids: tuple[Any, ...]


def normalize_label(text: str) -> str:
    return _WHITESPACE.sub(" ", text.strip().casefold())


def _strip_query_prefix(query: str) -> str:
    remainder = normalize_label(query)
    remainder = _PREFIX.sub("", remainder).strip()
    remainder = _ARTICLE.sub("", remainder).strip()
    remainder = _ARTICLE.sub("", remainder).strip()
    return remainder


def precise_label_match(
    query: str,
    items: Sequence[tuple[Any, str]],
    *,
    scores: dict[Any, float] | None = None,
) -> Unique | Miss | Ambiguous:
    remainder = _strip_query_prefix(query)
    if not remainder:
        return Miss()

    normalized_items = [(item_id, normalize_label(label)) for item_id, label in items]

    exact = [item_id for item_id, label in normalized_items if label == remainder]
    if len(exact) == 1:
        return Unique(exact[0])
    if len(exact) > 1:
        return Ambiguous(tuple(exact))

    named: list[Any] = []
    for item_id, label in normalized_items:
        tokens = label.split()
        long_enough = len(label) >= 8 or len(tokens) >= 2
        if long_enough and label and label in remainder:
            named.append(item_id)
    if len(named) == 1:
        return Unique(named[0])
    if len(named) > 1:
        return Ambiguous(tuple(named))

    if len(remainder.split()) < 2:
        word_hits = [
            item_id
            for item_id, label in normalized_items
            if remainder in label.split()
        ]
        if len(word_hits) == 1:
            return Unique(word_hits[0])
        if len(word_hits) > 1:
            return Ambiguous(tuple(word_hits))
        return Miss()

    if scores:
        ranked = sorted(
            ((item_id, score) for item_id, score in scores.items()),
            key=lambda pair: pair[1],
            reverse=True,
        )
        if ranked:
            best_id, best = ranked[0]
            runner = ranked[1][1] if len(ranked) > 1 else 0.0
            if best >= 0.88 and runner < 0.80:
                return Unique(best_id)

    return Miss()
