# Research: Memory Prompt Constitution (Phase 141)

## 1. Always-on reviewed facts vs profile facets

**Decision:** Always-on means `memory_facts` rows with `reviewed=true` AND `contradicted=false`, unioned with `CompanionPolicy` similarity hits, then token-budgeted (reviewed first, remainder to retrieved). Profile facets (`memory_profile_facets`) stay as today in identity’s “who this user is” block.

**Rationale:** Spec says reviewed profile facts, not a new store. Phase 140 remember writes `reviewed=true`. Onboarding seeds already reviewed.

**Alternatives considered:** Dump all facts — rejected. Only facets, not reviewed facts — would miss `remember_fact`. Always-on entire reviewed set without budget — could blow context; budget reviewed first is safer.

## 2. Prompt order

**Decision:** `_build_system_prompt` emits: datetime → shared constitution (memory honesty, no unsolicited fact mentions, apply facts silently) → agent job (`agent_instructions`) → identity biography (`build_identity_block` with formatted memory) → existing extras (screen, recap, open priorities, skills, procedures) remain around the job as today except biography must not precede constitution+job.

Concretely: stop passing formatted memory into a prefix that sits *before* agent instructions. Identity builder is called *after* constitution+job, or identity is split so traits/constitution stay short and “Known facts” is appended last.

**Rationale:** Spec FR-004. Current code does `datetime + identity(including memory) + instructions`.

**Alternatives considered:** Put constitution inside identity template only — specialists would inherit Ze-who but companion job would still sit after a huge biography if memory stays in the prefix. Must move memory after job.

## 3. Formatter dialect

**Decision:** Drop `provenance == "synthesized"` string check. Format `Provenance` enum, `confidence`, and recency from `created_at` (add to `Fact` projection if needed).

**Alternatives considered:** Keep raw/synthesized English — contradicts 134.

## 4. Unsolicited mentions

**Decision:** Constitution + companion copy only. No new component type. Tests that `TurnSurfacing` / `surface_loops` are unchanged (no fact chips).

## 5. Specialists

**Decision:** They inherit constitution+order+formatter. Do not edit calendar ISO-8601 (etc.) instruction strings in this phase.
