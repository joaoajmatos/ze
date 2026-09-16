# Research: Memory Admission (Phase 140)

## 1. Extraction gate shape

**Decision:** Rewrite `_SYSTEM` in `ze_memory/extractor.py` to a keep/drop JSON object (or array that is empty unless keep), with a closed `family` enum. Empty turns and ephemeral/commitment families return `[]`. Copy the conservative tone of `ze_worldstate/extraction.py`, but do **not** import worldstate from ze-memory (dependency direction).

**Rationale:** Open-loop already proved “usually []”. A shared library would couple cognition packages without a doctrine mandate.

**Alternatives considered:** (a) Heuristic-only, no LLM — too weak for preference language. (b) Shared gate package — extra package for one prompt. (c) Keep current free predicates — rejected by spec.

Closed families for this phase: `identity`, `preference`, `relationship`, `constraint`, `contact_detail`. Drop: `ephemeral`, `commitment`, `schedule`, `mood`, `other`.

## 2. Explicit write door

**Decision:** Replace `AgentResult.memory_proposals` with companion tools. Delete the field from `AgentResult` and all persist/merge in `write_memory` (including subtask harvest). Update tests; no alias, no dual-read.

**Rationale:** Grep shows no production producer; 125 already noted the field unused. Spec forbids a dual door.

**Alternatives considered:** Wire proposals as the remember path — rejected (tools are the speech act). Keep field empty forever — still a second door waiting to be misused.

## 3. remember_fact / forget_fact

**Decision:** `@tool` in `ze_personal/agents/companion/tools.py`. `remember_fact(predicate, value)` builds `Fact(reviewed=True, provenance=PROMPT_SUPPLIED, claim_kind=FACT)` and `submit_perception_facts`. Return `{ok, fact_id}` or `{ok: false, error}` — companion instructions MUST only confirm on `ok`.

`forget_fact(query)` finds non-contradicted facts by predicate equality or embedding/NLI match (reuse existing contradiction thresholds), then marks `contradicted=true` via a private store method (same SQL family as NLI contradiction). Does **not** skip the seam on remember; forget is a retraction of an existing perception fact, not a new FACT contribution — log as store update, not a second ungated insert.

**Rationale:** User-supplied writes are still perception facts. Forget is retraction, not a new claim kind.

**Alternatives considered:** REST-only remember — not conversational. Soft-delete column — extra migration without need (`contradicted` already hides from retrieval).

## 4. Eval fixtures

**Decision:** Add scenarios to `eval/scenarios/memory.yaml` (and unit tests that do not need a live graph): `remember`, `forget`, `ephemeral`, `constraint`, `commitment`. Commitment and ephemeral expect no new `memory_facts` row. Remember expects a row only if the environment can run tools (unit tests mock tool success separately from eval).

**Rationale:** Spec names these five speech acts. Existing `memory_store_explicit_fact` should be updated so “I’ll remember” is not required unless the tool succeeded — align criteria with FR-006.

## 5. Every-turn extraction remaining

**Decision:** Keep post-turn `extract_facts` after the gate. If the same turn already wrote via `remember_fact` for a predicate, extraction must not duplicate (drop overlapping predicates).

**Alternatives considered:** Remove extraction entirely — spec allows remaining if usually []. Removing would lose unprompted durable asides (“I prefer aisle seats” without “remember that”).
