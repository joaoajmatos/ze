"""Static checks that the lifecycle stays the only write surface (FR-007, FR-008, FR-009, SC-002)."""

from __future__ import annotations

import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "ze_worldstate"
REPO = Path(__file__).resolve().parents[4]

STORE_WRITES = (
    "create",
    "transition",
    "resolve",
    "link",
    "link_entity",
    "link_evidence",
    "set_confidence",
    "set_dismissed_evidence_fingerprint",
    "set_drift_deadline",
    "set_drift_rationale",
    "record_corroboration",
    "stamp_declared",
    "add_source",
    "promote",
    "mark_source_promoted",
)


def _source(path: Path) -> str:
    return path.read_text()


def test_the_store_defines_no_write_method():
    pattern = re.compile(rf"def ({'|'.join(STORE_WRITES)})\(")
    assert pattern.findall(_source(PACKAGE / "store.py")) == []


def test_the_store_does_not_hold_transition_tables():
    text = _source(PACKAGE / "store.py")
    for name in ("_ALLOWED_TRANSITIONS", "_USER_ASKED_TRANSITIONS", "_CONFIDENCE_STAMP"):
        assert name not in text


def test_the_declared_stamp_is_defined_once():
    owners = sorted(
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if re.search(r"\b0\.9\b", _source(path))
    )
    assert owners == ["lifecycle/rules.py"]
    fragments = sorted(
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if "drift_rationale = NULL" in _source(path)
    )
    assert fragments == ["lifecycle/rules.py"]


def test_the_closure_the_remap_and_the_threading_are_gone():
    gone = re.compile(
        r"commit_for|_LOOP_KIND|propose_loop_candidates|LoopGateDecision|_commit_admitted"
        r"|_create_declared_loop|_create_suspected_loop"
    )
    own = Path(__file__).resolve()
    offenders = []
    for root in ("core", "apps", "eval"):
        for path in (REPO / root).rglob("*.py"):
            if ".venv" in path.parts or "node_modules" in path.parts or path == own:
                continue
            if path.name in {"test_admission.py", "test_loop_judge.py"}:
                continue  # they assert the names are absent
            if gone.search(_source(path)):
                offenders.append(path.relative_to(REPO).as_posix())
    assert offenders == []


def test_review_and_decay_modules_are_deleted():
    assert not (PACKAGE / "review.py").exists()
    assert not (PACKAGE / "decay.py").exists()


def test_no_module_outside_the_lifecycle_writes_loop_rows():
    writes = re.compile(
        r"(UPDATE\s+open_loops|INSERT\s+INTO\s+open_loops"
        r"|INSERT\s+INTO\s+open_loop_sources|INSERT\s+INTO\s+memory_relationships)",
        re.IGNORECASE,
    )
    offenders = [
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if path.parent.name != "lifecycle"
        and "migrations" not in path.parts
        and writes.search(_source(path))
    ]
    assert offenders == []
