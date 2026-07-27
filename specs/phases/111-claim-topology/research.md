# Research: Claim Topology

**Input**: [spec.md](spec.md), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md),
[`specs/arch/plugin-domain-vocabulary.md`](../../arch/plugin-domain-vocabulary.md)
**Date**: 2026-07-27 (revised same day, after the spec's Provenance design was reworked per the
new ADR)

All items below were either resolved during `/speckit-clarify` (recorded in spec.md's
Clarifications section), forced by the `plugin-domain-vocabulary.md` ADR (recorded in spec.md's
Revision note and FR-002/FR-003), or required a read of the actual current implementation to
settle — no open unknowns remain.

## 1. Where `Signal` actually lives (correction to arch brief / spec framing)

**Finding**: `specs/arch/claim-topology.md` and the spec's Input line describe `Signal` as living
in `core/ze-plugin`. It does not. `Signal` (the dataclass with `source`, `magnitude`, `payload`,
etc.) is defined in `core/ze-memory/ze_memory/types.py`. `core/ze-plugin/ze_plugin/signals.py`
only holds the `SignalSource` Protocol (the `poll()` contract plugins implement) — it imports
`Signal` from `ze_memory.types` under `TYPE_CHECKING`, it doesn't define it.

**Decision**: FR-012/FR-013 target `ze_memory.types.Signal`, not a type in `ze-plugin`. The
`SignalSource` Protocol in `ze-plugin` is unchanged (per FR-014) — it just returns objects of
this now-richer shape. This doesn't change any requirement's substance (the four
`SignalSource` implementers still populate the two new fields), only the file path tasks.md
must target: `core/ze-memory/ze_memory/types.py`, not a `ze-plugin` module.

**Alternatives considered**: Treat the arch brief as authoritative and look for a second
`Signal`-like type in `ze-plugin` to retrofit instead. Rejected — `grep -rn "class Signal\b"`
across the repo returns exactly one definition, and `ze-plugin`'s own `pyproject.toml` doesn't
depend on anything that would let it own a competing claim-producer type; `ze-memory` is the
correct, sole home.

## 2. `Provenance`'s scope: doctrine-closed axis vs. plugin-owned inflow channel

**Finding**: `specs/arch/claim-topology.md`'s original design and this spec's first draft (FR-002)
folded `ze-worldstate`'s `LoopProvenance` (`conversation`, `email`, `calendar`, `ingestion`,
`user_declared`) into the same closed core `Provenance` enum as the doctrine's four epistemic
categories (`graph_recall`, `live_search`, `prompt_supplied`, `synthesized`). Re-reading
`specs/arch/ze-doctrine.md` §The epistemic ontology directly shows the doctrine's own formal
`Provenance` vocabulary is only those four values — `conversation`/`calendar`/`email`/`ingestion`
appear in the doctrine's claim-kind table only as illustrative *typical sources* for facts, never
as a second formal vocabulary. `LoopProvenance` conflated two axes the doctrine keeps separate:
epistemic origin (closed, doctrine-mandated) and inflow channel (open-ended, operational).

Separately, `email`/`calendar` are literally `ze-messenger`/`ze-calendar` domain vocabulary —
baking them into `core/ze-agents` would violate Principle III (core has no domain knowledge) and
require a core PR for every future plugin's inflow channel.

**Decision** (formalized in `specs/arch/plugin-domain-vocabulary.md`, an ADR + constitution
amendment): split the two axes. `ze_agents.claims.Provenance` stays exactly the doctrine's four
values (FR-002). Inflow-channel tagging becomes a plain `str` field, owned by whichever core
module or plugin produces the claim, validated by nobody at the core boundary (FR-003). Only
`OpenLoop` carries this concept among this feature's four producers — see §3.

**Alternatives considered**: An open/registry-extensible core enum (plugins register new
`Provenance` members at startup). Rejected in the ADR — `StrEnum` doesn't support clean runtime
member registration, and the machinery cost isn't justified when a plain string already works
and matches existing precedent (`Signal.source`, `SignalSource.source_key`).

## 3. `OpenLoop.provenance`'s retrofit: enum → string, with a compatibility audit

**Finding**: `ze_worldstate/inflow.py::make_loop_extractor_from_parts`'s docstring already
documents that plugin callers (`ze-messenger`, `ze-calendar`, `ze-ingestion`) "must not import
`ze_worldstate` directly," so the function signature already accepts `provenance: str` at the
plugin boundary — the boundary was already string-typed. But
`ze_worldstate/extraction.py::propose_loop_candidates` immediately does `prov =
LoopProvenance(provenance)`, coercing that string against the closed 5-value enum and raising
`ValueError` for anything unrecognized.

A full-repo grep (`grep -rn "LoopProvenance\." core/ze-worldstate/ core/ze-correlation/
apps/ze-api/ plugins/`) across both production code and every test file found only two of the
five enum values are ever referenced by name anywhere outside the enum's own declaration:
`LoopProvenance.CONVERSATION` and `LoopProvenance.USER_DECLARED` — both inside
`ze_worldstate/extraction.py`'s own special-case logic (the declared-loop fast path) and in
test fixtures constructing `OpenLoop` instances. `EMAIL`, `CALENDAR`, and `INGESTION` are never
pattern-matched anywhere; they exist only as declared enum members.

**Decision**: `OpenLoop.provenance` retypes to plain `str` (FR-003). `LoopProvenance` is
retained, not as a `StrEnum`, but as a plain class exposing string-constant attributes for the
two core-owned values `extraction.py` actually branches on (`CONVERSATION`, `USER_DECLARED`)
plus `INGESTION` (the third core-owned inflow, unused in branching today but core-owned by
definition — not a plugin's domain), e.g.:

```python
class LoopProvenance:
    CONVERSATION = "conversation"
    INGESTION = "ingestion"
    USER_DECLARED = "user_declared"
```

This is a plain namespace, not an `Enum` subclass — `LoopProvenance.CONVERSATION` still equals
the string `"conversation"`, so every existing call site (`provenance=LoopProvenance.CONVERSATION`
in production code and eleven test files) keeps working unchanged, string equality comparisons
(`if prov == LoopProvenance.CONVERSATION`) keep working unchanged, and no `ValueError`-raising
coercion exists anymore — `propose_loop_candidates` uses the incoming string directly instead of
calling `LoopProvenance(provenance)`. `EMAIL`/`CALENDAR` are dropped as declared constants;
`ze-messenger`/`ze-calendar` pass the literal strings `"email"`/`"calendar"` directly, exactly as
they already do at the plugin boundary today — no plugin-side code change required, only the
core-side validation removal.

**Alternatives considered**: Keep `LoopProvenance` as a `StrEnum` but make it "open" by catching
the `ValueError` and falling back to storing the raw string. Rejected — this keeps a
half-enforced whitelist that's neither a real closed set nor an honest open string, and still
requires a core code change to add `EMAIL`/`CALENDAR`-style *documented* values (the actual goal
is removing that requirement entirely, not softening its failure mode).

## 4. `EvidenceRef.origin`: confirmed as the correct (unaffected) use of the closed enum

**Finding**: `EvidenceRef.origin` (`core/ze-correlation/ze_correlation/types.py`) is currently
`Literal["graph_recall", "live_search", "prompt_supplied"]` — already exactly the doctrine's
epistemic-origin axis (missing only `synthesized`), never an inflow-channel concept. It describes
how a piece of evidence entered the correlation engine's reasoning, not which plugin produced the
underlying fact.

**Decision**: FR-008 is unaffected by the Provenance rework — `EvidenceRef.origin` correctly
retrofits onto the narrowed, doctrine-closed `Provenance` enum. This is the one place in this
feature where the shared closed enum is the right fit, confirming (rather than contradicting) the
split decided in §2.

## 5. `OpenLoop`'s `decay.py` refactor onto the shared `EVIDENCE_WEIGHTED` function

**Finding** (confirms clarification answer, unaffected by the Provenance rework):
`ze_worldstate/decay.py::cascade_from_evidence` implements the evidence-retraction cascade
inline: floor `0.05`, and `new_confidence = max(floor, old_confidence * remaining / total)` when
evidence remains, else floor. This is exactly the math FR-005 says the shared
`EVIDENCE_WEIGHTED` profile must match.

**Decision**: The shared `decay()` function in `ze_agents/claims.py` takes the cascade
computation itself (the confidence arithmetic only — floor clamp, weighted recompute).
`cascade_from_evidence` keeps everything else unchanged: fetching affected loops, the
`DRIFTING` state transition on evidence contradiction, and all logging. Only the line computing
`new_confidence` changes from inline arithmetic to a call into the shared function. This keeps
`ze_worldstate/tests/test_decay.py`'s existing assertions (`CONFIDENCE_FLOOR`,
`set_confidence.assert_awaited_once_with(...)`) valid unmodified — the public behavior of
`cascade_from_evidence` does not change, only what implements one internal line.

## 6. `memory_facts`' decay is a bulk SQL `UPDATE`, not a per-row Python call — how does FR-011 apply?

**Finding** (unaffected by the Provenance rework): `DreamPromoter._run_confidence_decay` in
`core/ze-memory/ze_memory/dream/promoter.py` does the decay entirely in one SQL statement:
`confidence = GREATEST(0.0, confidence - 0.03)` plus two `CASE` expressions setting
`reviewed`/`contradicted` at the 0.50/0.25 cliffs, scoped to
`provenance = 'synthesized' AND corroborated = false AND created_at < now() - interval '30 days'
AND contradicted = false`. There is no per-row Python object in this path.

**Decision**: Fetch-decay-write in Python, calling the shared function per row — a SQL query
that merely borrows constants from Python is still a second implementation of the decay *shape*
(the `GREATEST`/`CASE` cliff logic), just with imported numbers. The dream pipeline's
morning-integration pass already does one Python-side pass per run at the same low volume, so
adding a per-row fetch here is consistent with the pipeline's existing performance profile.
`_expire_stale_synthetic_facts` (the separate hard-expiry check) is untouched — it isn't decay,
it's a deadline cliff FR-011 doesn't mention.

## 7. FR-015's staleness helper vs. two SQL-side cutoff checks

**Finding** (unaffected by the Provenance rework): Only `stale_suspicion.py` computes its cutoff
in Python today. `ze_worldstate/store.py::list_drift_candidates` filters `drift_deadline <=
now()` in SQL; `ze_automation/goals/postgres.py::list_stuck` mixes an `idle_days` cutoff with a
separate `alert_cooldown_days` re-alert-suppression cutoff in a compound `HAVING` clause — only
the former is FR-015's concern.

**Decision**: Move the "is this past its cutoff" decision for all three jobs into Python via the
shared helper — safe at single-user scale (`open_loops`/`goals` never approach a size where
client-side filtering matters). Each store method drops its cutoff predicate but keeps its
state-filter predicate; the job calls the shared `is_stale(timestamp, window_days, now=...)`
helper per candidate. `stuck_goals`' unrelated cooldown-suppression cutoff stays in SQL — FR-015
only asks for the "is this stale" decision to be shared.

## 8. Precedent for a new shared-contract module in `ze-agents`

**Finding** (unaffected by the Provenance rework): `ze-agents` already holds `nli.py` (an
`NLIClient` Protocol) as a small, dependency-free shared contract module reused by both
`ze-memory` and `ze-correlation` — the same shape `claims.py` needs.

**Decision**: `ze_agents/claims.py` is a new, single file: two `StrEnum`s (`ClaimKind`,
`Provenance` — the latter now exactly four values per §2), one `Confidence` dataclass, one
`DecayProfile` `StrEnum`, and one `decay()` function dispatching on `decay_profile`. No new
package, no new dependency — mirrors `nli.py`'s existing footprint exactly.

## 9. Package dependency audit (confirms SC-005, no new edges)

**Finding** (unaffected by the Provenance rework): All four producer packages —
`ze-worldstate`, `ze-correlation`, `ze-memory`, `ze-plugin` — plus `ze-automation` and
`ze-proactive` already declare `ze-agents` as a direct dependency.

**Decision**: SC-005 is satisfiable with zero `pyproject.toml` changes.
</content>
