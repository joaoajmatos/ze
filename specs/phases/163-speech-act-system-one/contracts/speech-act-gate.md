# Contract: Speech-act gate

**Feature**: `163-speech-act-system-one`
**Verbatim**: `speech_act`, `fact`, `forget`, `reminder`, `loop`, `goal`, `ingest`, `drop`, `clarify`, `admit_speech_act`, `admit_family`, `SpeechAct`, `KEEP_FAMILIES`, `SystemOneClient`

## Entry point

`ze_memory.extractor.gather_fact_proposals(configurable, *, agent, prompt, response) -> list[Fact]` (signature unchanged).

Reads from `configurable`: `openrouter_client` (wording + legacy), `system_one_client`, `settings`, optional `admission_judgments` (list sink).

## Flow

1. No `openrouter_client` → `[]`.
2. Response starts with `[ERROR]` or `is_trivial_turn(prompt)` → `[]` (no System One call).
3. If `system_one_client` present and `thresholds_from_settings(...)` is not `None`:
   - One `evaluate({"user": prompt, "assistant": response[:1000]}, questions)`.
   - `hold` → `[]`. No LLM call.
   - `admit` → one wording call; result passes through `_admit_parsed` with the fixed family; `fact.agent = agent`.
   - `skip` → fall through to 4.
4. Legacy `extract_facts` (pre-163), once.

## Questions (stable order)

| id | type | options |
|---|---|---|
| `speech_act` | choice | `fact, forget, reminder, loop, goal, ingest, drop, clarify` |
| `family` | choice | `identity, preference, relationship, constraint, contact_detail, drop` |
| `biography` | noul | yes = durable self-fact, no time attached |

Criteria include Portuguese examples. State is `{user, assistant}` only (assistant capped at 1000 chars).

## Invariants

- Label filters are `admit_speech_act` / `admit_family` only; unknown → drop / `None`.
- A hold never triggers the legacy judge; only a skip does.
- Same-turn identity skip (148) and the contribution seam run after the gate, unchanged.
- Default tests never call a real System One or LLM endpoint.
