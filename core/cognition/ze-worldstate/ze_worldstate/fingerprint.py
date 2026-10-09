from __future__ import annotations

import hashlib

from ze_plugin.contribution import EvidenceRef


def compute_evidence_fingerprint(evidence_refs: list[EvidenceRef]) -> str:
    """Stable hash of a set of evidence refs (FR-011's dismissed-then-re-implied check)."""
    key = "|".join(
        sorted(f"{ref.kind}:{ref.id}" for ref in evidence_refs)
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
