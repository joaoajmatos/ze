# System One models — living roadmap

> **Status:** Living. Phases [162](../phases/162-system-one-client/spec.md)–[164](../phases/164-routing-choice-after-e5/spec.md) Implemented; the first four surfaces are on in the shipped config with calibrated bars: 163 (2026-10-09), 164 as fixed by phase [167](../phases/167-routing-choice-criteria/spec.md) (2026-10-12), and 166 (2026-10-12). See [docs/system-one.md](../../docs/system-one.md) for the reader-facing summary. Phase [166](../phases/166-skill-suggestion-system-one/spec.md) (O3) specified and implemented; enabled 2026-10-12. Phase [168](../phases/168-loop-extraction-gate/spec.md) (O4, loop extraction gate) is specified and in progress; it is enabled in the shipped config (2026-10-12) after an `ENABLE` verdict on the held-out set for English and Portuguese. Phase [172](../phases/172-corroboration-promotion/spec.md) (corroboration promotion) is implemented; its surface ships off with null bars after a held-out `KEEP OFF` on 2026-10-15. Later opportunities in this document wait for their own phase.
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
2. **Code owns arithmetic, policy, and execution.** Budgets, write confirmation (phase 181 replaced `CapabilityGate` modes), SQL, confirm WebSocket protocol, decay, push claim-then-notify, `allowed_tools` intersection, date/window math — never a model.
3. **Local E5 stays the shortlist.** Cosine is similarity, not calibrated confidence. System One may **select** after a shortlist; it does not replace `query:` / `passage:` encoding. *(167: when the recall gate needs the whole roster, E5 no longer filters for the routing Choice and remains only the 160 cosine skip path; see the 167 recall table in `specs/phases/167-routing-choice-criteria/research.md`.)*
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
| Haiku JSON | Extractor `speech_act` (fallback since 163; labels `fact, forget, ingest, clarify, none` since 173), loop `is_loop` (fallback since 168), router decompose | Closed labels in the prompt; no calibrated P(label). Phase 148 left a “hard classifier” as later L. |
| Heuristic | Complexity regex, conductor gather/act sets, constraint veto tokens, honesty regex | Cheap and often correct; not semantic. |

Calibrated **act / hold / escalate** is missing on routing, admission, confirms, push, and dream promotion. Human confirm (`AWAIT_CONFIRMATION`) is the right escalate path when a judgment is unsure — do not invent a parallel review product.

---

## Opportunity catalog

> **O1 implementation notes (163):** System One cannot write text, so on persist a narrowed Haiku value writer phrases the fact value only (family comes from System One, fixed confidence 0.8). The speech-act surface makes a single System One attempt via `evaluate(..., max_attempts=1)`; the global default stays three attempts for 164 to choose. Unsure answers hold with no Haiku tie-break; only a client skip, malformed answer or uncalibrated bar runs the old judge. The surface ships off with null bars.

> **O2 implementation notes (164):** E5 stays the shortlist (`shortlist_k`, default 5). One batched request asks the agent Choice (shortlist ∪ `none`), a multi-specialist Noul and a complexity Score, with a single attempt (`evaluate(..., max_attempts=1)`). Three separate bars (`choice_trust`, `multi_specialist_hold`, `complexity_lookup_max`) ship `null`; the surface stayed off until `make calibrate-routing` (enabled by 167, see below). `routing_log.confidence` is the Choice peakedness when a Choice was consumed, not the cosine score (drift fix). Score maps to a model tier: at or below `complexity_lookup_max` is simple, above is complex; the Score tier is kept through Haiku `decompose`. A `none` Choice or a high Noul sends the turn to decompose; an unsure Choice or a skip falls back to the E5 bars and the regex estimator. Both router call sites use one factory, `build_embedding_router`.

> **O2 implementation notes (167):** The 164 surface failed held-out checks (about 0.98 confident, 80% right) because companion and research both claimed "explain X", the `none` criterion was weak, and E5 recall was low. 167 removed the claim from companion's description; added an optional `routing_criteria` on `BaseAgent` (use-for / not-for text; the Choice falls back to `description`; E5 still embeds `description`); and rewrote the Choice instructions and `none` criterion without naming any plugin agent. `shortlist_k` is now chosen by an offline recall sweep: k=9 of a 10-agent roster, the smallest with recall >= 0.95 on `routing`, `routing_holdout` and `routing_holdout2`. Acceptance rule (FR-009, amended in the spec): zero harmful trusts, ECE <= 0.10 and zero research->companion misses on both held-out sets; raw accuracy is reported, not gating. Result: enabled with `choice_trust` 0.5, `multi_specialist_hold` 0.5, `complexity_lookup_max` null (regex tiering stays). Follow-up: a loops-vs-companion criteria refinement.

> **O2 implementation notes (182):** 182 replaced the routing Score with a separate tier judgment. Routing no longer asks a complexity question. The regex `ComplexityEstimator`, `complexity_lookup_max` and `RoutingEnvelope.complexity` are removed. Routing always assigns the agent's full model. A new `choose_tier` node runs after `match_skills`. It asks one System One Noul, `needs_deep_reasoning`, with one attempt, and only for a single-agent turn whose agent declares a `model_simple` that differs from its `model`. The shipped `system_one.surfaces.complexity` is on (`enabled: true`, `simple_max: 0.40`), enabled 2026-10-16 after the held-out ENABLE. The code default without a config block is off (`ComplexitySurfaceConfig()` is disabled). With `enabled: false` or `simple_max: null`, every agent runs its full model and makes no request.

> **O3 implementation notes (166):** The roadmap name is "skill suggestion", but nothing is suggested to the user. The phase gates **automatic application**. E5 stays the shortlist, with a lower shortlist-only pre-floor (`shortlist_floor`, near 0.35) under `match_threshold`, and `shortlist_k` set from the offline recall table, not assumed. One batched request (`evaluate(..., max_attempts=1)`) asks a Choice over the shortlist ∪ `none` and a Noul `needs_skill`. Pure code decides apply, drop, abstain or skip. At most one automatic skill applies (a deliberate narrowing of 114's "all matched skills"); explicit `/skill-name` bypasses the judgment and still stacks. A below-`match_threshold` apply is marked on the trace (`below_floor`). `match_skills` appends its judgment rows to `state["judgments"]` and never replaces `embed_route`'s rows. Two bars (`choice_trust`, `needs_skill_hold`) ship `null`; the surface stayed off until `make calibrate-skills`; enabled 2026-10-12 with `choice_trust` 0.75, `needs_skill_hold` 0.6, `shortlist_k` 5. Off, uncalibrated, skipped or unsure: the 114 result is unchanged.

> **O4 implementation notes (168):** The Haiku `is_loop` call is split into a gate and a writer. One batched System One request (`evaluate(..., max_attempts=1)`) asks three Nouls: `is_open_concern`, `resolves_existing`, and, on conversation only, `explicit_declaration`. Three bars (`loop_hold`, `resolves_hold`, `explicit_hold`) shipped `null` until `make calibrate-loop-gate`; they are now 0.75, 0.8 and 0.85. Pure code in `ze_worldstate/loop_judge.py` (`decide()`) maps the answers to resolve, create-declared, create-suspected, hold or fallback. Haiku only writes the title after a positive gate, and also returns an optional `implied_window_days` on creates. Matching, dismissal fingerprints, confidence, provenance, drift arithmetic and the contribution seam stay in code. Parsing the window from the text in code is a later phase; until then the window comes from the Haiku writer. The conversation gate runs in `write_memory` beside the fact extractor, appends its rows to `MessageTrace.judgments`, and commits fire-and-forget; the worldstate `conversation_memory_hook` is deleted. Email, calendar and ingestion run the same gate, can create suspected loops or resolve existing ones, log their judgments, and write no message-trace rows. Off, uncalibrated, skipped, invalid or missing answers run the 109 Haiku gate unchanged. **Finding:** that gate was inert. It parses the reply with `json.loads`, Haiku wraps its JSON in a ```json fence, and all 136 calibration replies (88 tuned, 48 held-out) failed to parse, so loop extraction created no loops in production before 168. The calibration ran against the gate unchanged, with a fence-tolerant copy of the same prompt as the baseline; afterwards the fallback's parse was fixed with the shared fence-tolerant helper. **Result (held-out, one run, 10 positives per language):** English System One precision 1.00, recall 10/10, zero false creates; Haiku (fence-tolerant) precision 0.90, recall 9/10, one false create. Portuguese System One precision 1.00, recall 10/10, zero false creates; Haiku 0.909, 10/10, one false create. Not gating: one Portuguese false resolve; false declared 0 for System One against 3 for Haiku. The counts are small, so the comparison is coarse. One recorded asymmetry: the Haiku fallback still honors an explicit declaration on non-conversation text, as in 109; a later phase should cut it.

Cascade: **(1)** System One gates an LLM **(2)** LLM generates, System One selects **(3)** System One verifies **(4)** System One routes **(5)** scores become ranking features.

### Specified now

| # | Opportunity | Current | Shape | Cascade | vs E5/NLI | Effort | Phase |
|---|---|---|---|---|---|---|---|
| O0 | Client, DI, trace, fail-open | Nothing | Protocol sibling of `NLIClient` | — | New layer | S–M | **162** |
| O1 | Speech-act + keep/drop | Haiku JSON every turn | Choice `{fact,forget,reminder,loop,goal,ingest,drop,clarify}` + family Choice + Noul biography | 4 + 1 (wording) | **Replace LLM judge**; keep `admit_*` | M | **163** |
| O2 | Agent after E5 shortlist + complexity | Cosine-as-confidence; regex complexity; Haiku on low gap | Choice shortlist ∪ `none`; Score complexity | 4 + 1 (decompose) | **Complement E5**; keep decompose | M | **164 (Implemented); 167 (Implemented, enabled)** |
| O3 | Skill gating after E5 shortlist | Every skill with cosine ≥ 0.5 applies, plus `/slug` | Choice shortlist ∪ `none`; Noul `needs_skill`; `/slug` stays code | 1 | **Complement E5**; keep `/slug` | M | **166 (Implemented)** |
| O4 | Loop extraction gate | Haiku JSON `is_loop` | Three Nouls (`is_open_concern`, `resolves_existing`, `explicit_declaration`); Haiku writes the title and window only after a positive gate | 1 + 2 (title) | **Replace LLM judge**; keep matching, dismissal, drift | M | **168 (Implemented; enabled)** |
| O4c | Conversation commitment intake | Two batches per turn (163 speech-act + 168 loop gate) that never saw each other | One batch: commitment Choice `{reminder,loop,goal,waiting_on,fact,forget,ingest,clarify,none}` + family Choice + Noul biography + Nouls `is_open_concern`, `explicit_declaration`, `resolves_existing`; pure `decide()` merges them with the turn's tool calls and links loops to reminders and goals | 1 + 2 (title, fact value) | **Replace** the O1 and O4 conversation paths; keep the 163 fact rules, the 168 loop rules and the Haiku writers; O1 and O4 stay for fallback and for the non-conversation inflows | M–L | **173 (Implemented; enabled)** |
| O4b | Suspected-loop corroboration | A match on a `suspected` loop links the evidence and does nothing else | One Noul `same_concern` on an independent match; two bars (corroborate, promote); `open_loop_sources` provenance | 1 | **Complement E5/matching**; E5 is the shortlist via `find_matching_loop`, independence and arithmetic stay in code | M | **172 (Implemented; ships off)** |
| O11 | Model tier for one agent turn | Regex word-count tier; routing Score tier (164) | One Noul `needs_deep_reasoning` in `choose_tier`, after `match_skills`; one attempt; `model_simple` only when the answer is at or below `simple_max`; full model otherwise | 1 | **Complement routing**; the full model is the default on off, skip, invalid or uncalibrated | S–M | **182 (Implemented; enabled 2026-10-16 at `simple_max` 0.40 after a held-out ENABLE in EN and PT)** |

### Queued (do not start before their own phase)

| # | Opportunity | Notes |
|---|---|---|
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
2. **163 — Speech-act System One (Implemented)** — Replace the Haiku admission **judge**. Keep typed `admit_speech_act` / `admit_family`, trivial-turn regex, dual-write skip, contribution seam. In-turn companion tools unchanged except they consume the same closed set.
3. **164 — Routing Choice after E5 (Implemented)** — Shortlist in code; Choice ∪ `none`; complexity Score; Haiku decompose only when Choice says `none` or confidence is too low or a multiple-specialist Noul is high. 153/155 conductor rewrite unchanged.

4. **166 — Skill gating (Implemented)** — Shortlist in code; Choice ∪ `none` plus Noul `needs_skill`; one automatic skill; `/skill-name` unchanged; trace marks below-floor applies. Depends on 162; reuses the 163/164 patterns, not their bars.

5. **168 — Loop extraction gate (Implemented)** — Three Nouls gate extraction; Haiku writes the title and window only after a positive gate; the conversation gate runs in `write_memory`, other inflows run the gate, log judgments, and write no trace rows; enabled 2026-10-12 with `loop_hold` 0.75, `explicit_hold` 0.85, `resolves_hold` 0.8 after an `ENABLE` verdict for EN and PT. Depends on 162; reuses the 163/166 patterns, not their bars.

7. **173 — Commitment intake (Implemented)** — one request per conversation turn replaces the 163 speech-act and 168 conversation loop-gate requests; a turn that created a reminder or goal creates no loop and links it (`zw004`); `waiting_on` is a label only; `make calibrate-commitment-intake`; enabled 2026-10-16 with `choice_hold` 0.7, `family_hold` 0.7, `biography_hold` 0.55, `loop_hold` 0.6, `explicit_hold` 0.95, `resolves_hold` 0.8 after an `ENABLE` verdict for EN and PT on a third blind held-out set (two earlier sets returned `KEEP OFF` and are spent). The 168 loop gate keeps two Nouls for email, calendar and ingestion and drops `explicit_hold`. Depends on 163 and 168.

6. **172 — Corroboration promotion (Implemented)** — one Noul `same_concern` on an independent suspected-loop match; two bars set the loop's confidence or promote it to `active`; code owns independence and the arithmetic; provenance in `open_loop_sources` (`zw003`); ships off after a held-out `KEEP OFF` (2026-10-15). Depends on 162; reuses the 168 patterns, not its bars.

7. **182 — Complexity routing (Implemented; enabled at `simple_max` 0.40)** — Routing always assigns the full model. A tier Noul (`needs_deep_reasoning`) in `choose_tier`, after `match_skills`, picks `model_simple` for a light single-agent turn. The complexity Score and the word-count classifier are removed. The held-out run on 2026-10-16 returned ENABLE in English and Portuguese at `simple_max` 0.40. The user approved enabling, and the shipped config sets `enabled: true`. Depends on 162; reuses the 164 judgment pattern, not its bars.

Later: O5 retrieval → O6 push → O7/O8 reflection verify → O9/O10 plugins.

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
preprocess → embed_route → [decompose] → fetch_context → match_skills → choose_tier → preflight
  → execute_tool → correlate → surface_loops → [synthesize] → record_trace → write_memory
```

| Surface | Today | 162–164, 166, 168 |
|---|---|---|
| `EmbeddingRouter` | E5 cosine τ/gap | **164 Implemented** — Choice after shortlist (System One, E5 fallback) |
| `ComplexityEstimator` | regex + word count | 182: tier Noul after match_skills; full model on off/skip |
| Haiku `decompose` | JSON subtasks | **164 Implemented** — gated on `none` / multi-specialist; not deleted |
| `SkillMatcher` | E5 shortlist, System One Choice + Noul (166), `/slug` in code | **166 Implemented** — 114 path on skip, abstain or off |
| Write confirmation (181; was `CapabilityGate`) / budget | lookup + USD | never |
| `live_rerank` | DeBERTa as relevance | queued O5 |
| Extractor `speech_act` | System One (163), Haiku fallback | **163 Implemented** |
| Write-time NLI | DeBERTa contradiction | keep |
| Inline loops | entity overlap, no τ | keep (policy) |
| `passes_push_bar` | numeric τ + NLI | queued O6 |
| Loop extraction | Haiku `is_loop` | **168 Implemented** — three Nouls gate, Haiku title writer; Haiku `is_loop` on fallback |
| Loop corroboration | Link evidence only (170) | **172 Implemented** — Noul `same_concern`; promote above the bar |
| Correlate / dream | LLM + NLI/Sonnet | queued O7/O8 |

Proactive: `CorrelationJob` (LLM), `AttentionArbitrationJob` (rank; `PushSweepJob` is **removed**). Drift/stale/decay jobs are time/math only.

---

## Appendix B — File index (evidence)

| Symbol | Path |
|---|---|
| `EmbeddingRouter` | `core/engine/ze-core/ze_core/routing/router.py` |
| `ComplexityEstimator` (removed by 182) | `ze_core/routing/complexity.py` |
| Tier judgment (`needs_deep_reasoning`, `decide_tier`, bar, `build_tier_question`) | `ze_core/routing/tier.py` |
| `choose_tier` node | `ze_core/orchestration/nodes/tier.py` |
| Haiku decompose | `ze_core/routing/fallback.py` |
| `NLIClient` | `core/contracts/ze-agents/ze_agents/nli.py` |
| `LocalNLIClient` | `ze_core/nli.py` |
| Extractor / `speech_act` | `ze_memory/extractor.py` |
| `live_rerank` | `ze_memory/retrieval_rerank.py` |
| `SkillMatcher` | `ze_skills/matching.py` |
| `passes_push_bar` | `ze_worldstate/surfacing.py` |
| Loop gate (`decide()`, questions, bars) | `ze_worldstate/loop_judge.py` |
| `LoopInflow` (gate + commit, title writer) | `ze_worldstate/admission.py` |
| Loop corroboration (independence rule, effects) | `ze_worldstate/corroboration.py` |
| Corroboration judge (`same_concern`, bars, `decide()`) | `ze_worldstate/corroboration_judge.py` |
| Loop extraction (109 Haiku gate, fallback) | `ze_worldstate/extraction.py` |
| `MessageTrace` | `ze_core/conversation/messages/types.py` |
| `CapabilityGate` (removed by 181; `preflight` in `ze_core/orchestration/nodes/execution.py` replaces it) | `ze_core/capability/gate.py` (removed) |
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

> **164 tuning notes:** The first live run (model `typesafe/jev-1.13`, 56 rows) gave Choice accuracy 0.87 EN / 0.91 PT. Every miss was a research turn sent to companion or `none`, and research was outside the top-4 shortlist in 3 cases. The Score arrives as the expected level index (0 lookup, 1 single_tool, 2 multi_hop), not a [0, 1] value; the judge now divides it by 2, so `complexity_lookup_max` stays on [0, 1]. Gold-agent shortlist recall (`python eval/calibration/routing.py --recall`, offline, no credits) was 0.826 at k=4 and 0.870 at k=5; after rewriting the research description it is 0.870 at k=4 and 0.957 at k=5, so `shortlist_k` defaults to 5. No `choice_trust` bar was safe on that run; bars stay `null` until the next live run.

> **172 tuning notes:** Run 2026-10-15 by the ENG lead with `make calibrate-corroboration` (model `typesafe/jev-1.13`; 84 tuned rows, 42 EN + 42 PT; 47 held-out, 24 EN + 23 PT). Question wording unchanged from R4. On the tuned set, precision is 1.000 at every bar and no negative scores above 0.5, so the grid cannot separate corroborate from promote by false promotions; the ENG lead chose `corroborate_hold` 0.6 and `promote_hold` 0.8 (scores of 0.8 or more are 32 of 32 gold-same; recall 0.91 at 0.6), a deliberate departure from R9's arithmetic made before the held-out run. The E5 title-cosine baseline at 0.75 matches every row (tuned precision 0.524 / recall 1.000; held-out precision 0.574 / recall 1.000), so its recall is a ceiling, not a rival. Held-out verdict, one run at 0.6 / 0.8: EN ENABLE (precision 1.000, recall 14 of 14, zero false promotions); PT KEEP OFF (precision 1.000, recall 12 of 13 = 0.923, below the E5 recall minus 0.05); overall KEEP OFF. The surface ships off with null bars, and the held-out set is spent for these bars. Follow-ups: a larger held-out set per language, an absolute recall floor, or a lower `corroborate_hold`.

> **182 tuning notes:** Tuning and freeze ran on 2026-10-16 with `make calibrate-complexity` (model `typesafe/jev-1.13`, `timeout_ms` 2000, `max_attempts=1`, state from the production `build_tier_state`). The tuned set has 47 English and 47 Portuguese rows (`cx-001` to `cx-094`). The held-out set has 54 rows, 27 per language. Only the offline shape check ran over it before the verdict run, plus one aggregate state-size check that printed total characters only. Source: `specs/phases/182-complexity-routing/research.md`, R12.
>
> Tuning runs (bar and light counts; "false" means `full` rows judged light):
>
> | Run | State | Bar | EN false / light recall | PT false / light recall | Lowest `full` Noul |
> |---|---|---|---|---|---|
> | 1 | A: routing criteria as the `agent` field | 0.30 | 0 / 22 of 23 | 0 / 23 of 23 | 0.30 to 0.35 |
> | 2 | A, repeat | 0.30 | 0 / 22 of 23 | 0 / 23 of 23 | same band |
> | 3 | B: tools first, then description | 0.40 | 0 / 22 of 23 | 0 / 23 of 23 | 0.42 |
> | 4 | C: no `agent` field | 0.55 | 0 / 23 of 23 | 0 / 23 of 23 | 0.60 |
> | 5 | C on the final code | 0.55 | 0 / 23 of 23 | 0 / 23 of 23 | 0.56 |
> | 6 | C on the final code, at the frozen bar | 0.40 | 0 / 22 of 23 | 0 / 23 of 23 | 0.56 |
>
> **The `agent` field is dropped.** A (routing criteria) left a 0.30 to 0.35 floor under the `full` rows. B (description and tool names, tools first) was worse: its light outlier at 0.43 sat above its lowest `full` row at 0.42. C opened a clear gap: lowest `full` 0.56 to 0.60, highest `simple` 0.44 to 0.47. The field describes scope, not difficulty, so it went (spec FR-006, amended 2026-10-16). The state builder no longer reads the agent registry.
>
> **Bar rule (FR-017, amended).** Pick the bar on the tuned set only. No tuned `full` row may be judged light. The bar sits at least 0.15 below the lowest tuned `full` Noul. Tuned light recall is at least 0.8 per language. Among bars that pass, prefer the larger margin. The first rule drafted, the highest step below the lowest `full` row, gives 0.55 on run 5. That bar is 0.01 under the lowest `full` row, inside the measured noise of about 0.04.
>
> **Freeze.** `simple_max` = 0.40, frozen on 2026-10-16. On tuned run 6: zero `full` rows judged light; margin 0.16 to the lowest tuned `full` row (0.56); light recall EN 22 of 23 = 0.957, PT 23 of 23 = 1.000. Row `cx-039` sits at exactly 0.400 and counts as light, because a value equal to the bar is light.
>
> **Held-out verdict (T031, 2026-10-16).** One run over the blind held-out set at `simple_max` 0.40:
>
> | Language | False downgrades | Light recall | Skipped or invalid | Verdict |
> |---|---|---|---|---|
> | EN | 0 | 14 of 14 = 1.000 | 0 of 27 | ENABLE |
> | PT | 0 | 13 of 14 = 0.929 | 0 of 27 | ENABLE |
>
> Overall ENABLE. Latency, reported and not gated: EN p50 550 ms and p90 880 ms; PT p50 552 ms and p90 985 ms.
>
> **Portuguese near-miss (caveat).** The lowest PT `full` row lies between 0.40 and 0.50. It was not judged light at 0.40, so it sits within 0.10 of the bar. The tuned lowest `full` was 0.56 to 0.60. So the held-out margin is smaller than the tuned margin of 0.16 suggested. Single rows move up to about 0.04 between runs on the tuned set, about half of that gap. The held-out set is spent for this bar and instruction text, and it cannot be re-scored to measure the margin. The user approved enabling; the shipped config sets `enabled: true` at `simple_max` 0.40 (2026-10-16).
