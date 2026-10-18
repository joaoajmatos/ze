"""Test setup shared by the ze-agents suite."""

from __future__ import annotations

import hashlib
import sys
import types

try:  # the stub lane merges after the harness lane; a fake keeps these tests independent
    import ze_agents.script_stub  # noqa: F401
except ImportError:  # pragma: no cover
    _fake = types.ModuleType("ze_agents.script_stub")

    def _build_stub(schemas: list[dict]) -> str:
        names = sorted(s["function"]["name"] for s in schemas)
        return "\n".join(f"def {n}(**kw): pass" for n in names) + (
            "\ndef propose(tool, **a): pass\ndef finish(r, writes=None): pass\n"
        )

    def _source_hash(source: str) -> str:
        return hashlib.sha256(source.encode()).hexdigest()

    _fake.build_stub = _build_stub  # type: ignore[attr-defined]
    _fake.source_hash = _source_hash  # type: ignore[attr-defined]
    sys.modules["ze_agents.script_stub"] = _fake
