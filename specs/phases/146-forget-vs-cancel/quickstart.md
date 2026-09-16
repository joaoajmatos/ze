# Quickstart: 146 forget vs cancel

Phase 142 routing table and Phase 143 forget gate already exist. This phase retargets cancel speech.

## Implementer order

1. Extractor tests: “forget the dentist” → `reminder` (or `loop`/`goal` as seeded), not `forget`; aisle-seat forget stays `forget` (`test_speech_act_gate.py`).
2. `precise_label_match` unit tests, then the helper in `ze_agents`.
3. Hard-cut `run_delegate` result to `{response, tool_calls}`; fix delegate tests.
4. Loops agent wrapping `close_loop` / `drop_loop` + list; wire import paths.
5. Reminders/goals: list → match → at most one write; instruction + tests.
6. Companion R14 instructions; honesty gate for domain claims vs 143 forget.
7. Eval: companion “forget the dentist” vs `memory_forget_explicit`.
8. `make test-memory`, `make test-personal`, `make test-calendar`, `make test-automation`, `make test-worldstate`, `make lint`.

## Manual check

- Seed reminder “Call the dentist” and fact “dentist named Ana.” Utter “forget the dentist.” Reminder gone; fact live; reply may confirm cancel, not “I’ve forgotten that.”
- “Forget that I prefer aisle seats” with the same reminder still pending → fact retracted; reminder remains.
- Two dentist reminders, short “forget the dentist” → none cancelled; ask or miss.

## Out of scope while implementing

Phase 144 mail/calendar veto, 145 recitation, 147 ingest honesty, 148 extractor races, 149 specialist constitution bundle, `/memories` filesystem.
