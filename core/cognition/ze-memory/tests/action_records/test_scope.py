from __future__ import annotations

import pathlib


def test_no_generic_arbitration_or_signal_rewire_in_action_records() -> None:
    root = pathlib.Path(__file__).resolve().parents[1] / "ze_memory" / "action_records"
    for path in root.rglob("*.py"):
        text = path.read_text()
        assert "signal_sources" not in text
        assert "arbitr" not in text.lower()
        assert "dual_write" not in text
        assert "propose_facts" not in text
