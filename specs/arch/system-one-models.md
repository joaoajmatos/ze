# System One models — living roadmap

> **Status:** Living. Phases [162](../phases/162-system-one-client/spec.md)–[164](../phases/164-routing-choice-after-e5/spec.md) specified (Draft). Later opportunities in this document wait for those three; do not start them in the 162 tree.
> **Date:** 2026-09-30
> **Related:** [Ze Doctrine](ze-doctrine.md), [Contribution Seam](contribution-seam.md), [Memory Honesty Roadmap](memory-honesty-roadmap.md), [Claim Topology](claim-topology.md), [OpenRouter Gateway](openrouter-gateway.md), [Local Embeddings](local-embeddings.md), [Pre-v1 Hard Cuts](pre-v1-hard-cuts.md), NLI [080](../phases/080-nli-client/spec.md), speech-act [142](../phases/142-speech-act-routing/spec.md)–[148](../phases/148-extractor-dual-write/spec.md), E5 routing [160](../phases/160-e5-routing-confidence/spec.md)

This is a **cross-cutting architecture note**, not a package spec and not a single phase. It records where typed System One judgments (TypeSafe Jev and equivalents) may sit beside OpenRouter LLMs and local E5 / DeBERTa, what must stay in code, and the order of implementable slices.

---

## Why this lives in `arch/`, not `core/` or a phase

| Home | What it is for | Why not here |
|---|---|---|
| `specs/core/` | What one **package** owns (`ze-agents`, `ze-memory`, …) | System One is not a package. After 162 ships, `ze-agents.md` lists the Protocol the same way it lists `NLIClient`. |
| `specs/phases/` | One implementable slice | This document sequences many slices. 162–164 are the first three. |
| `specs/arch/` | Cross-cutting decision + living sequence | Same role as [memory-honesty-roadmap.md](memory-honesty-roadmap.md) and [companion-conductor-roadmap.md](companion-conductor-roadmap.md). |

When a later opportunity (skills, retrieval classify, loops, dream, plugins) is ready, add a phase spec and a row in **Sequencing** below. Do not relitigate the pinned decisions in that phase.

---

## What System One is (do not confuse with LLMs)

System One models return **typed judgments and calibrated probabilities**, not free text. Code owns the workflow. Three primitives:

| Primitive | Answer | Use when |
|---|---|---|
| **Choice** | One of a closed set; full distribution + confidence (peakedness) | Agent, speech-act, skill, claim-kind |
| **Noul** | P(yes) only — no separate confidence; ~0.5 means undecided, not “medium” | Independent yes/no (biography? needs a skill? grounded?) |
| **Score** | Degree on ordered **descriptive** levels | Complexity, interrupt-worthiness — never exact measurement |

Authoritative provider docs: [TypeSafe index](https://docs.typesafe.ai/llms.txt), [OpenRouter System One](https://openrouter.ai/docs/api/api-reference/systemone/submit-a-system-one-request). Current flagship on OpenRouter: `typesafe/jev-1.13` (~100ms, input billed, output free). Pin that slug in config if thresholds are calibrated; do not pin `~typesafe/jev-latest`. The trace stores the **reported** model id (may be dated).

**Constitution Principle VII** still holds: **all generative LLM calls go through OpenRouter** via `LLMClient` (chat). System One is **not** an LLM and MUST NOT be sent as chat completions. OpenRouter hosts System One natively (`POST /api/v1/systemone`) on the same `OPENROUTER_API_KEY`. Do not add `TYPESAFE_API_KEY` or `typesafe-sdk`. Do not amend VII to “one AI vendor” — local E5/NLI stay. Phase 162 hard-cut the earlier “must not tunnel through OpenRouter” line once OpenRouter shipped the native path.

---

## Pinned (do not relitigate in a phase spec)

1. **OpenRouter remains System Two.** System One is an *additional* decision layer. No replacement of agent replies, drafts, research synthesis, or conductor planning.
2. **Code owns arithmetic, policy, and execution.** Budgets, `CapabilityGate` modes, SQL, confirm WebSocket protocol, decay, push claim-then-notify, `allowed_tools` intersection, date/window math — never a model.
3. **Local E5 stays the shortlist.** Cosine is similarity, not calibrated confidence. System One may **select** after a shortlist; it does not replace `query:` / `passage:` encoding.
4. **Local DeBERTa NLI stays for pair entailment/contradiction.** Write-time contradiction and consolidator NLI are the right primitive at zero API cost. Do not replace them with System One. Fail-open on non-Latin (`None` scores) is unchanged until a later phase measures otherwise.
5. **Fail open to the current path.** Timeout, missing key, 429/529 → behave as today (same contract as `live_rerank`). High-harm interrupts (ntfy) MAY fail closed in a later push phase; 162–164 fail open.
6. **Minimal state.** Named JSON fields only. No full `AgentState`, session dump, or DB row. Context rot is a documented Jev failure mode.
7. **One narrow question per judgment; batch independent questions.** Do not hide several decisions in one Choice. Do not transplant a Noul threshold onto a Choice.
8. **Doctrine posture stays code.** A Noul of 0.62 does not license surfacing a suspicion as a fact. Claim-kind licensing on `Contribution` is unchanged.
9. **Pre-v1 hard-cut.** No wrap-then-replace of `NLIClient` into a mega-protocol. `SystemOneClient` is a sibling of `NLIClient` / `LLMClient`.
10. **Cookbook numbers are examples.** Thresholds are validated on Ze data (including Portuguese). Pin `typesafe/jev-1.13` (or a later measured OpenRouter slug) when calibrating.

---

## Fit analysis (ground truth from code)

Ze already makes semantic forks with four mechanisms. Almost none are calibrated judgments.

| Mechanism | Where | Honest output? |
|---|---|---|
| E5 cosine | Routing (`ROUTING_THRESHOLD` 0.73 / gap 0.02), skills (0.5), retrieval floor 0.35, loop match 0.75, novelty 0.85 | Similarity. `RoutingEnvelope.confidence` is this cosine — a naming lie vs doctrine confidence. |
| DeBERTa NLI | Write-time contradiction ≥ 0.60, `live_rerank` (`entailment + 0.5 * neutral`), push grounding, news/finance opt-in | Entailment/contradiction. Misused as **relevance** on the retrieve path. Latin/ASCII ≥ 80% or `None`. |
| Haiku JSON | Extractor `speech_act`, loop `is_loop`, router decompose | Closed labels in the prompt; no calibrated P(label). Phase 148 left a “hard classifier” as later L. |
| Heuristic | Complexity regex, conductor gather/act sets, constraint veto tokens, honesty regex | Cheap and often correct; not semantic. |

Calibrated **act / hold / escalate** is missing on routing, admission, confirms, push, and dream promotion. Human confirm (`AWAIT_CONFIRMATION`) is the right escalate path when a judgment is unsure — do not invent a parallel review product.

---

## Opportunity catalog

Cascade: **(1)** System One gates an LLM **(2)** LLM generates, System One selects **(3)** System One verifies **(4)** System One routes **(5)** scores become ranking features.

### Specified now

| # | Opportunity | Current | Shape | Cascade | vs E5/NLI | Effort | Phase |
|---|---|---|---|---|---|---|---|
| O0 | Client, DI, trace, fail-open | Nothing | Protocol sibling of `NLIClient` | — | New layer | S–M | **162** |
| O1 | Speech-act + keep/drop | Haiku JSON every turn | Choice `{fact,forget,reminder,loop,goal,ingest,drop,clarify}` + family Choice + Noul biography | 4 + 1 (wording) | **Replace LLM judge** (LLM now only words admitted facts); keep `admit_*` | M | **163** (Implemented; surface off until bars calibrated) |
| O2 | Agent after E5 shortlist + complexity | Cosine-as-confidence; regex complexity; Haiku on low gap | Choice shortlist ∪ `none`; Score complexity | 4 + 1 (decompose) | **Complement E5**; keep decompose | M | **164** |

### Queued (do not start in 162–164)

| # | Opportunity | Notes |
|---|---|---|
| O3 | Skill suggestion | E5 ≥ 0.5 or `/slug`. Cookbook: Choice + Noul `needs_skill` after shortlist. Keep `/slug` in code. |
| O4 | Loop extraction gate | Haiku JSON `is_loop`. Noul `is_open_concern`; title still generated; windows in **code**. |
| O5 | Passage classify | After ANN + floor; Nouls relevant/usable/conflicts. Cap candidates so latency stays in the live-rerank class or use the async cache path. Keep DeBERTa write-time NLI. |
| O6 | Push interrupt Score | Features into `AttentionArbitrationJob`; budget and claim-then-notify stay code. Inline mentions stay ungated (FR-006). |
| O7 | Dream citation + critic Nouls | Gate1 complement; support counts **code** (Jev does not count). Do not inherit critic “ambiguous → PASS”. |
| O8 | Correlation citation check | After LLM hypothesis; Choice per cited snippet. ID membership stays code. |
| O9 | Outbound constraint Nouls | Per reviewed constraint, iterate in code. Clock windows stay parsed in code. After O1. |
| O10 | News/finance same-item | Measure vs local NLI on English before replacing. |

### Non-fits (never a System One job)

Agent/specialist replies; email/outreach draft; research/briefing prose; conductor multi-hop plan text; `delegate_to_agent` fat briefs; workspace shell/files; decompose sub-prompts; spend USD; CapabilityGate; confirm protocol; write-time contradiction NLI; inline loop mentions.

---

## Sequencing

Implement **in order**. 163 and 164 both need 162; they do not need each other. Do not start 163 in the 162 tree. Do not start 164 in the 163 tree.

1. **162 — System One client** — Protocol, engine implementation, DI, config, `MessageTrace` judgments, fail-open, no production behavior change if disabled.
2. **163 — Speech-act System One** — Replace the Haiku admission **judge**. Keep typed `admit_speech_act` / `admit_family`, trivial-turn regex, dual-write skip, contribution seam. In-turn companion tools unchanged except they consume the same closed set.
3. **164 — Routing Choice after E5** — Shortlist in code; Choice ∪ `none`; complexity Score; Haiku decompose only when Choice says `none` or confidence is too low or a multiple-specialist Noul is high. 153/155 conductor rewrite unchanged.

Later: O3 skills → O4 loops → O5 retrieval → O6 push → O7/O8 reflection verify → O9/O10 plugins.

---

## Architecture sketch (normative for 162)

| Piece | Home | Rule |
|---|---|---|
| `SystemOneClient` Protocol | `ze_agents` | Sibling of `NLIClient`; not an extension of `LLMClient` |
| Re-export | `ze_sdk` | Plugins import Protocol from `ze_sdk`, never `ze_core` |
| HTTP implementation | `ze_core` | Same layer as `LocalNLIClient` / OpenRouter |
| DI | `ze_api` / engine `dep_map` | Same map pattern as `NLIClient` |
| Config | `config.yaml` `system_one:` | `enabled`, pinned model id, timeout, per-surface flags |
| Secret | `.env` `OPENROUTER_API_KEY` | Same key as chat; server-side only |
| Trace | `MessageTrace.judgments` | question id, primitive, answer, probabilities, peakedness, model, tokens, latency, `consumed` |
| Tests | mock client | Default `make test` MUST NOT call OpenRouter System One |

**Never in plugins:** budgets, capability modes, SQL, confirm protocol.

**Cost:** Jev is cheap vs Haiku **judges** (speech-act, `is_loop`). It is never cheaper than local E5/NLI for pure similarity or English pair entailment.

---

## Evaluation and calibration

- Speech-act: existing `memory_speech_act_*` plus a labeled EN+PT slice. Metrics: exact act, fact-row precision/recall, ECE on Choice confidence.
- Routing: `eval/scenarios/routing.yaml` + conductor; log Choice vs E5 disagreement; EN+PT clear singles still skip decompose when Choice agrees.
- Do not ship cookbook τ (`AUTO_ACCEPT=0.8`, skill-suggestion tables).
- Randomize Choice option order in **eval only**; production order stable (doctrine order for speech_act).
- Re-calibrate when the pinned model id changes.

---

## Anti-patterns (Ze-specific)

- Surfacing a suspicion because a Score said “push now.”
- Unsolicited biography because a retrieval Noul said relevant (phase 145 is a reply gate).
- Silent wrong admit because Choice picked the closest of eight labels with no `drop`.
- Double ntfy: judgments sit **before** shared budget claim, never after send.
- Replacing `CapabilityGate` with “is this dangerous.”
- Asking the model whether spend exceeds a dollar amount.
- Dumping episode bodies or full skills into `state`.
- Treating cosine, NLI entailment, LLM JSON `confidence`, Ze claim `Confidence` (decaying), and Choice peakedness as one number.

---

## Appendix A — Turn decision surface

```
preprocess → embed_route → [decompose] → fetch_context → match_skills → capability_check
  → execute_tool → correlate → surface_loops → [synthesize] → record_trace → write_memory
```

| Surface | Today | 162–164 |
|---|---|---|
| `EmbeddingRouter` | E5 cosine τ/gap | 164 Choice after shortlist |
| `ComplexityEstimator` | regex + word count | 164 Score |
| Haiku `decompose` | JSON subtasks | 164 gated; not deleted |
| `SkillMatcher` | E5 0.5 or `/slug` | queued O3 |
| `CapabilityGate` / budget | lookup + USD | never |
| `live_rerank` | DeBERTa as relevance | queued O5 |
| Extractor `speech_act` | Haiku JSON | **163** |
| Write-time NLI | DeBERTa contradiction | keep |
| Inline loops | entity overlap, no τ | keep (policy) |
| `passes_push_bar` | numeric τ + NLI | queued O6 |
| Loop extraction | Haiku `is_loop` | queued O4 |
| Correlate / dream | LLM + NLI/Sonnet | queued O7/O8 |

Proactive: `CorrelationJob` (LLM), `AttentionArbitrationJob` (rank; `PushSweepJob` is **removed**). Drift/stale/decay jobs are time/math only.

---

## Appendix B — File index (evidence)

| Symbol | Path |
|---|---|
| `EmbeddingRouter` | `core/engine/ze-core/ze_core/routing/router.py` |
| `ComplexityEstimator` | `ze_core/routing/complexity.py` |
| Haiku decompose | `ze_core/routing/fallback.py` |
| `NLIClient` | `core/contracts/ze-agents/ze_agents/nli.py` |
| `LocalNLIClient` | `ze_core/nli.py` |
| Extractor / `speech_act` | `ze_memory/extractor.py` |
| `live_rerank` | `ze_memory/retrieval_rerank.py` |
| `SkillMatcher` | `ze_skills/matching.py` |
| `passes_push_bar` | `ze_worldstate/surfacing.py` |
| `MessageTrace` | `ze_core/conversation/messages/types.py` |
| `CapabilityGate` | `ze_core/capability/gate.py` |
| SDK re-export | `packages/ze-sdk/ze_sdk/__init__.py` |

Defaults: `ze_agents/defaults.py` (`ROUTING_THRESHOLD` 0.73, gap 0.02); `apps/ze-api/config/config.yaml` (`memory.*`, `skills.match_threshold` 0.5).

---

## Appendix C — Glossary

| Term | Meaning here |
|---|---|
| Choice / Noul / Score | System One primitives (above) |
| ClaimKind | Doctrine `IDENTITY/FACT/INFERENCE/SUSPICION/PRIORITY` — what is **held**, not a router label |
| Provenance | Where a claim came from — never a model judgment |
| Ze claim confidence | Stored 0–1 **with decay** |
| Choice confidence | Distribution peakedness — not permission to act |
| E5 “confidence” | Cosine — do not confuse with either of the above |

---

## Open questions (measure before later phases)

1. In-turn companion vs 163 post-turn judge disagreement rate before coupling them.
2. Whether Choice `none` on routing means E5 *k* is too small.
3. Whether passage classify fits the 120ms live-rerank budget (else async only).
4. Push: fail closed on System One outage? (Not 162–164.)
5. Portuguese calibration before enabling 163/164 for that locale.
6. TypeSafe data handling vs biography text in `state` (prefer zero retention if offered).
