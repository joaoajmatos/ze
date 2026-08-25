"""Contribution seam — the shared write-path contract every producer of a claim speaks.

`SourceFunction` and `TargetFace` are doctrine-mandated closed sets (the seven cognitive
functions and four world-state faces from `specs/arch/ze-doctrine.md`), matching the same
Principle III carve-out that makes `ze_agents.claims.ClaimKind`/`Provenance` core-owned
enums rather than plugin-domain vocabulary.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, TypeVar
from uuid import UUID

from ze_agents.claims import ClaimKind, Confidence, Provenance
from ze_agents.errors import (
    DanglingEvidenceError,
    MissingEvidenceError,
    UnlicensedClaimKindError,
)
from ze_logging import get_logger

log = get_logger(__name__)

T = TypeVar("T")

_EVIDENCE_REQUIRED_KINDS = frozenset({ClaimKind.INFERENCE, ClaimKind.SUSPICION})


class SourceFunction(StrEnum):
    PERCEPTION = "perception"
    MEMORY = "memory"
    EXECUTIVE = "executive"
    SOCIAL_COGNITION = "social_cognition"
    REFLECTION = "reflection"
    ACTION = "action"
    GOVERNANCE = "governance"


class TargetFace(StrEnum):
    SELF = "self"
    USER = "user"
    WORLD = "world"
    ACTIVE_CONCERNS = "active_concerns"


_LICENSE: dict[SourceFunction, frozenset[ClaimKind]] = {
    SourceFunction.PERCEPTION: frozenset({ClaimKind.FACT}),
    SourceFunction.MEMORY: frozenset(),
    SourceFunction.EXECUTIVE: frozenset(
        {
            ClaimKind.IDENTITY,
            ClaimKind.FACT,
            ClaimKind.INFERENCE,
            ClaimKind.SUSPICION,
            ClaimKind.PRIORITY,
        }
    ),
    SourceFunction.SOCIAL_COGNITION: frozenset(),
    SourceFunction.REFLECTION: frozenset({ClaimKind.INFERENCE, ClaimKind.SUSPICION}),
    SourceFunction.ACTION: frozenset(),
    SourceFunction.GOVERNANCE: frozenset(),
}


@dataclass
class EvidenceRef:
    kind: Literal["fact", "episode", "signal"]
    id: UUID


@dataclass
class Contribution:
    claim_kind: ClaimKind
    provenance: Provenance
    confidence: Confidence
    target_face: TargetFace
    source_function: SourceFunction
    evidence: list[EvidenceRef] = field(default_factory=list)


async def validate_and_submit(
    contribution: Contribution,
    write: Callable[[], Awaitable[T]],
    *,
    check_fact_exists: Callable[[UUID], Awaitable[bool]] | None = None,
    check_episode_exists: Callable[[UUID], Awaitable[bool]] | None = None,
    check_signal_exists: Callable[[UUID], Awaitable[bool]] | None = None,
) -> T:
    """Validate `contribution`'s licensing and evidence, then delegate to `write()`.

    Never replaces the caller's store write — only gates it. Raises a typed
    `ContributionError` subclass and logs a `contribution_rejected` warning before
    raising if validation fails.
    """
    licensed = _LICENSE.get(contribution.source_function, frozenset())
    if contribution.claim_kind not in licensed:
        log.warning(
            "contribution_rejected",
            source_function=contribution.source_function,
            claim_kind=contribution.claim_kind,
            reason="unlicensed_claim_kind",
        )
        raise UnlicensedClaimKindError(
            f"{contribution.claim_kind!r} is not licensed for "
            f"{contribution.source_function!r}"
        )

    if contribution.claim_kind in _EVIDENCE_REQUIRED_KINDS and not contribution.evidence:
        log.warning(
            "contribution_rejected",
            source_function=contribution.source_function,
            claim_kind=contribution.claim_kind,
            reason="missing_evidence",
        )
        raise MissingEvidenceError(
            f"{contribution.claim_kind!r} contribution requires non-empty evidence"
        )

    checkers: dict[str, Callable[[UUID], Awaitable[bool]] | None] = {
        "fact": check_fact_exists,
        "episode": check_episode_exists,
        "signal": check_signal_exists,
    }
    for ref in contribution.evidence:
        checker = checkers.get(ref.kind)
        exists = await checker(ref.id) if checker is not None else False
        if not exists:
            log.warning(
                "contribution_rejected",
                source_function=contribution.source_function,
                claim_kind=contribution.claim_kind,
                reason="dangling_evidence",
            )
            raise DanglingEvidenceError(
                f"evidence {ref.kind}:{ref.id} does not exist"
            )

    return await write()
