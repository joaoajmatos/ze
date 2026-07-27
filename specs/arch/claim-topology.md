# Claim Topology — One Vocabulary for Confidence, Kind, and Provenance

> **Status:** Proposed (design-only — no implementation until ratified)
> **Scope:** `core/ze-agents` (new shared home), `core/ze-memory`, `core/ze-correlation`,
> `core/ze-worldstate`, `core/ze-plugin` (all four current claim producers).
> **Constrained by:** `specs/arch/ze-doctrine.md` §The epistemic ontology,
> §The contribution model.
> **Relationship to the contribution seam:** narrower and more urgent than
> `specs/arch/contribution-seam.md`. That brief is about *arbitrating* proposals between
> functions — still correctly design-only on the arbitration mechanism itself, no real conflict
> exists yet. This brief is about the **data shape** every claim already has, informally, four
> different ways. It does not require arbitration, a queue, or a new orchestration seam — it
> only requires one type definition and one decay function, reused instead of reinvented. It is
> a prerequisite for the seam: the `Contribution` type resolved in `contribution-seam.md`
> (§Resolved: `Signal` is a `Contribution` subtype) is built directly on the `ClaimKind` /
> `Provenance` / `Confidence` vocabulary defined here.

---

## Why this exists

A mapping pass across every reflective/proactive mechanism in the codebase (six job families —
automation, correlation, worldstate, memory consolidation, dream, notifications — plus the two
seam-shaped producers, `SignalSource` and loop extraction) found that the doctrine's own
taxonomy — claim-kind, provenance, confidence-with-decay — has been implemented **four
times, four different ways**, instead of once:

| Producer | Type | Confidence | Claim-kind | Provenance |
|---|---|---|---|---|
| `ze-plugin` (`SignalSource`) | `Signal` | **none** — only `magnitude: float` (relevance, not confidence) | none | `source: str` (plugin key) |
| `ze-worldstate` (loops) | `OpenLoop` | `confidence: float`, evidence-weighted decay, floor 0.05 | `LoopClaimKind` — **verbatim doctrine enum**: identity/fact/inference/suspicion/priority | `LoopProvenance`: conversation/email/calendar/ingestion/user_declared |
| `ze-correlation` (hypotheses) | `Hypothesis` / `EvidenceRef` | `confidence: float`, **no decay job — frozen at generation time** | none on `Hypothesis` (implicit by type) | `EvidenceRef.origin: Literal["graph_recall","live_search","prompt_supplied"]` — missing `"synthesized"` |
| `ze-memory` (facts) | `memory_facts` row | `confidence: float`, linear decay (-0.03/30 days, only if `synthesized` + uncorroborated), hard cliffs at 0.50/0.25 | none (implicit — facts are always "fact" by table identity) | `provenance: str` (`raw`/`synthesized`) + separate `source: str` (`user_asserted`/`ze_observed`) |

Only one of the four (`OpenLoop`) actually implements the doctrine's claim-kind taxonomy. The
other three either have no confidence field, no claim-kind field, a differently-named
provenance vocabulary, or — in `Hypothesis`'s case — a confidence value that **never decays**,
which is a direct, live violation of the doctrine's "everything decays" rule
(`ze-doctrine.md` §Belief revision), not a hypothetical one.

Separately, three independent modules reimplement the same "has this gone stale" shape —
`ze_worldstate/jobs/stale_suspicion.py`, `ze_worldstate/drift.py`'s drift sweep, and
`ze-automation`'s `stuck_goals.py` — all `cutoff = now - window_days; if past cutoff,
transition state`, written three separate times with no shared code.

This is not a case for the full contribution seam (no two functions are colliding over the same
world-state face yet — that trigger genuinely hasn't fired). It is a case for finishing what
`OpenLoop` already did correctly and applying it everywhere else.

---

## What ships

### 1. A shared claim vocabulary in `ze-agents`

`ze-agents` is the lowest common dependency of all four current producers (`ze-memory`,
`ze-correlation`, `ze-worldstate`, `ze-plugin` all depend on it directly or transitively) and
already holds other shared developer-facing contracts (`LLMClient` protocol, `Settings`,
`ZeError` hierarchy). A new `ze_agents/claims.py` module holds:

- `ClaimKind` — `StrEnum`: `IDENTITY`, `FACT`, `INFERENCE`, `SUSPICION`, `PRIORITY`. Promoted
  verbatim from `LoopClaimKind`, which already matches the doctrine exactly.
- `Provenance` — `StrEnum`: `GRAPH_RECALL`, `LIVE_SEARCH`, `PROMPT_SUPPLIED`, `SYNTHESIZED`,
  plus the inflow-specific values currently scattered across `LoopProvenance`
  (`CONVERSATION`/`EMAIL`/`CALENDAR`/`INGESTION`/`USER_DECLARED`) — one enum, not two competing
  vocabularies for "where did this come from."
- `Confidence` — a small value type wrapping `value: float` (0–1) with a `decay_profile`
  discriminator (e.g. `EVIDENCE_WEIGHTED`, `TIME_LINEAR`, `FROZEN`⚠) and **one shared decay
  function**, `decay(confidence, elapsed, evidence_state) -> Confidence`, parameterized rather
  than reimplemented per store.

No new store, no new table, no orchestration change. This is a types-and-one-function change.

### 2. Retrofit the three existing producers to use it

- `OpenLoop`: swap `LoopClaimKind`/`LoopProvenance` for the shared `ClaimKind`/`Provenance` —
  it's the reference implementation, so this is a rename/re-export, not a redesign.
- `Hypothesis`/`EvidenceRef`: add `claim_kind` (always `INFERENCE` or `SUSPICION` depending on
  corroboration state — never `FACT`, enforcing the doctrine's "reflection never emits a fact"
  rule at the type level for the first time in this producer), fix `EvidenceRef.origin` to use
  the shared `Provenance`, and — the concrete bug fix this brief exists to justify — wire the
  shared decay function into a scheduled job so hypothesis confidence actually ages instead of
  being frozen forever.
- `memory_facts`: add `claim_kind` (`FACT` for raw/observed rows, `INFERENCE` for
  uncorroborated synthesized rows per the dream pipeline's existing distinction), replace the
  bespoke -0.03/30-day linear decay in `promoter.py` with the shared `TIME_LINEAR` profile
  (same math, now not reimplemented), and fold `provenance`/`source` into the shared
  `Provenance` enum.
- `Signal`: becomes a `Contribution` subtype per `contribution-seam.md`'s resolution — always
  `claim_kind=FACT` (the doctrine's sole license for perception), `provenance` populated from
  how the plugin sourced it, and a real `confidence` field it currently lacks entirely.
  `magnitude` stays as-is — it's a relevance score, a different concept, not confidence. The
  `SignalSource` Protocol and its four plugin implementers (calendar/finance/messenger/news)
  are unchanged; only the object they return gains this shape. `ze-correlation` and
  `ze-worldstate` keep polling `signal_sources()` exactly as today — no consumer rewiring here.

### 3. One shared staleness-sweep utility

Extract the `cutoff = now - window; past it → transition` shape shared by
`stale_suspicion.py`, `drift.py`'s sweep, and `stuck_goals.py` into a single helper (home:
`ze-proactive`, since that's what already owns the scheduler wrapper all three run under).
Each call site still owns its own transition semantics and window; only the "is this stale"
check is shared.

---

## What this explicitly does not do

- **Does not build the contribution seam.** No `Contribution` type, no arbitration step, no
  queue. `contribution-seam.md` remains correctly design-only — nothing here requires resolving
  its open questions (sync-vs-staged, arbitration mechanism). This brief only makes sure that
  *when* the seam is eventually built, it has one vocabulary to wrap instead of four.
- **Does not touch storage schemas beyond adding the missing `claim_kind` column** to
  `correlation_hypothesis` and `memory_facts` (both currently lack one). No table is dropped or
  merged.
- **Does not unify loops and goals**, or attempt a cross-mechanism attention budget. Those
  remain the open items already tracked in `docs/cognitive-architecture.md`'s sequencing
  section.
- **Does not change dream/consolidation's job registration.** They are legitimately two
  schedules over one substrate (confirmed: they already share the `memory_facts` table and the
  confidence field); this brief doesn't merge their jobs, just their confidence math.

---

## Consequences

- **Fixes a live doctrine violation** (frozen hypothesis confidence) as a side effect of
  unification, not as a separate fix — this is the concrete evidence that the duplication has
  real cost, not just aesthetic cost.
- **`OpenLoop` stops being the one correct implementation and becomes the reference everyone
  else matches** — validates the Phase 109/110 design instead of discarding it.
- **Reduces four vocabularies to one**, so the next producer (whatever it is) has an obvious
  thing to import instead of inventing a fifth.
- **Directly de-risks the eventual contribution seam** — when `contribution-seam.md`'s trigger
  condition is next revisited, the seam will be extracting arbitration logic over an already
  uniform data shape, not designing the data shape and the arbitration mechanism at once.

---

## Open Questions

- [ ] **Decay profile taxonomy** — is `EVIDENCE_WEIGHTED` / `TIME_LINEAR` / `FROZEN` (marked
  as a bug, not a valid third profile — everything must decay) the right initial set, or does
  `memory_facts`'s cliff behavior (hard `reviewed=false`/`contradicted=true` thresholds) need
  its own profile rather than reusing `TIME_LINEAR`?
- [ ] **Migration order** — retrofit `Hypothesis` first (fixes the live bug fastest) or
  `memory_facts` first (highest write volume, most exercised path)?
- [ ] **Backward compatibility** — do `LoopClaimKind`/`LoopProvenance` become re-exports of the
  shared enums (zero call-site churn in `ze-worldstate`) or are all call sites migrated to
  import from `ze_agents.claims` directly? Recommend re-export initially, direct import over
  time — consistent with "wrap before replacing" guidance already used elsewhere in this repo.
- [ ] **Does `Signal.magnitude` deserve its own doctrine-recognized concept** (relevance,
  distinct from confidence), or should it be renamed/reconciled once `Signal` carries a real
  `confidence` field alongside it?
</content>
