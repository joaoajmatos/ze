# ADR: Plugin-Owned Domain Vocabulary — Core Enums Stay Doctrine-Closed

> **Status:** Accepted
> **Date:** 2026-07-27
> **Scope:** `core/ze-agents` (`ClaimKind`/`Provenance`/`Confidence`), `core/ze-worldstate`
> (`LoopProvenance`), and any future core-owned closed vocabulary a plugin would need to extend.
> **Triggered by:** review of `specs/phases/111-claim-topology/spec.md`'s FR-002, which proposed
> folding `ze-worldstate`'s inflow-specific `LoopProvenance` values (`conversation`, `email`,
> `calendar`, `ingestion`, `user_declared`) into a single closed core `Provenance` enum.
> **Governs:** `specs/phases/111-claim-topology/spec.md` (reworked in the same session as this
> ADR) and every future spec that adds a value to a core-owned enum on a plugin's behalf.

---

## Context and Problem Statement

`specs/arch/claim-topology.md` proposes one shared `Provenance` enum in `core/ze-agents`,
covering both the doctrine's four epistemic source categories (`graph_recall`, `live_search`,
`prompt_supplied`, `synthesized`) and `ze-worldstate`'s five inflow-specific values
(`conversation`, `email`, `calendar`, `ingestion`, `user_declared`) — "one enum, not two
competing vocabularies for where did this come from."

Two of those five inflow values — `email` and `calendar` — are not core concepts. They are the
literal domain vocabulary of `plugins/ze-messenger` and `plugins/ze-calendar`. Baking them into
a `core/ze-agents` enum means every future plugin that produces claims through its own inflow
channel (`ze-finance`'s Trading212 sync, `ze-news`'s RSS poll, a future `ze-legal` filing feed)
requires a `core/ze-agents` code change to add its value — the exact dependency direction
Principle III forbids ("New capabilities that belong to a domain go in a plugin, not the
engine").

This is not hypothetical. The current wiring already shows the seam under strain:
`ze_worldstate/inflow.py::make_loop_extractor_from_parts` accepts `provenance: str` specifically
because its docstring says callers "(ze-messenger, ze-calendar, ze-ingestion) ... must not
import `ze_worldstate` directly" — the plugin boundary is already a bare string. But
`ze_worldstate/extraction.py::propose_loop_candidates` immediately does `prov =
LoopProvenance(provenance)`, which raises `ValueError` for any string not already in the closed
enum. A plugin can pass any string across the boundary; only a whitelisted few are accepted.
Widening that whitelist to a shared core enum makes the problem worse, not better — now two
packages must change together instead of one.

Separately: re-reading `specs/arch/ze-doctrine.md`'s own definition (§The epistemic ontology)
shows the doctrine's `Provenance` vocabulary is *only* `graph_recall` / `live_search` /
`prompt_supplied` / `synthesized` — the epistemic origin of a claim at the point of reasoning
(recalled vs. searched vs. stated vs. derived). `conversation`/`calendar`/`email`/`ingestion`
appear in the doctrine's claim-kind table only as illustrative *typical sources* for facts, not
as a second formal vocabulary. `LoopProvenance`'s five-value enum conflates two different axes
that the doctrine itself keeps separate: **epistemic origin** (doctrine-mandated, closed) and
**inflow channel** (operational, open-ended, plugin-owned).

---

## Decision Drivers

- Principle III: core has no domain knowledge; plugins extend via `ze_sdk.*`, never the reverse
- Every plugin added since Phase 20 (calendar, messenger, prospecting, finance, news) has
  introduced its own inflow/source vocabulary; nothing about that trend stops
- The doctrine's own formal `Provenance` vocabulary is narrower than what `LoopProvenance`
  encodes — conflating the two axes was already a latent inconsistency this feature would have
  promoted to core, not fixed
- Existing extensibility precedent in this repo — `ZePlugin.agent_module_paths()`,
  `SignalSource.source_key`, `Signal.source: str` — never requires a core enum edit to add a
  new plugin; each uses a plugin-declared string or a `Protocol`, not a closed core enum

---

## Considered Options

1. **One closed core enum covering both axes** (as originally proposed in FR-002) — simplest to
   write once, but requires a core PR for every new plugin inflow channel, forever.
2. **Open/registry-extensible core enum** — plugins register new `Provenance` members into a
   runtime registry at startup (mirroring `SignalSource` collection). Technically possible but
   `StrEnum` doesn't support runtime member registration cleanly in Python; would require
   replacing the enum with a registry-backed value type everywhere it's used for pattern-
   matching (`EvidenceRef.origin`, `extraction.py`'s `if prov == ...` branches) — more machinery
   than the problem justifies at this scale.
3. **Split the two axes: closed doctrine `Provenance`, open plugin-owned inflow string** — core
   keeps exactly the doctrine's four epistemic categories as a closed enum (nothing about those
   four is plugin-specific — they describe how a claim entered reasoning, not which plugin
   produced it); the inflow-channel concept becomes a plain string, supplied and owned by
   whichever core module or plugin produced the claim, never validated against a core-owned
   whitelist.

---

## Decision Outcome

**Chosen option: 3 — split the two axes.**

- `ze_agents.claims.Provenance` (the doctrine-mandated, closed vocabulary) stays exactly the
  four values `ze-doctrine.md` names: `GRAPH_RECALL`, `LIVE_SEARCH`, `PROMPT_SUPPLIED`,
  `SYNTHESIZED`. No plugin ever needs a fifth value here — these describe an epistemic
  relationship to reasoning, not a data source, and the doctrine treats the set as closed.
- Inflow/channel tagging (which mechanism produced a claim — conversation, email, calendar,
  ingestion, a future plugin's sync job) is **not a `Provenance` at all**. It travels as a plain
  `str` field, supplied by whichever core module or plugin constructs the claim, with no core
  enum, no core-side coercion, and no whitelist rejection. Core-owned inflows (`conversation`,
  `ingestion`) and the one doctrine-relevant special case (`user_declared`, which changes
  `ze-worldstate`'s extraction fast-path — see Consequences) are documented string constants,
  not enum members; plugin-owned inflows (`email`, `calendar`, and whatever a future plugin
  introduces) are that plugin's own string, chosen and documented by the plugin, never requiring
  a core code change.
- **General rule, stated for reuse beyond this ADR:** a value belongs in a core-owned closed
  enum only if the *doctrine itself* mandates the closed set (confidence decay profiles, claim
  kinds, the four epistemic provenance categories). A value that names *which plugin or channel*
  produced something is plugin-domain vocabulary and must never be hardcoded into a core enum —
  it travels as a string (or a plugin-local enum the plugin owns), the same way `Signal.source`
  and `SignalSource.source_key` already work.

### Positive Consequences

- Adding a new plugin inflow channel (a fifth `SignalSource` implementer, a new communication
  channel) never requires a `core/ze-agents` or `core/ze-worldstate` PR.
- Fixes a real doctrine-fidelity gap as a side effect: `Provenance` in core now matches
  `ze-doctrine.md`'s actual four-value definition instead of a five-value superset the doctrine
  never specified.
- `ze_worldstate/extraction.py::propose_loop_candidates` stops raising `ValueError` for any
  inflow string a plugin didn't know was missing from a whitelist it can't see — the plugin
  boundary that was already string-typed in `inflow.py` becomes honestly string-typed all the
  way through.

### Negative Consequences / Trade-offs

- Loses `LoopProvenance`'s current exhaustive-enum type safety for inflow values — a typo'd
  inflow string (`"emial"`) is no longer caught by a `ValueError` at the boundary. Mitigated by:
  each plugin should define its own local constant (or a plugin-local `StrEnum`, e.g.
  `ze_communication.ChannelType` already does this for messaging channels) for the inflow string
  it emits, so typos are caught by that plugin's own type-checking, not by core.
- `ze_worldstate.extraction`'s one doctrine-relevant special case (`user_declared` triggering
  the declared-loop fast path) becomes a string comparison (`prov == "user_declared"`) instead
  of an enum-member comparison — functionally identical, slightly weaker at author-time
  (no IDE autocomplete on the literal), acceptable given it is one call site.

---

## Links

- `specs/arch/ze-doctrine.md` §The epistemic ontology — the four-value `Provenance` definition
  this decision restores fidelity to
- `specs/arch/claim-topology.md` — the design brief this ADR corrects (FR-002's original
  single-enum proposal)
- `specs/phases/111-claim-topology/spec.md` — reworked in the same session to reflect this
  decision
- `core/ze-worldstate/ze_worldstate/inflow.py::make_loop_extractor_from_parts` — existing
  precedent showing the plugin boundary was already string-typed before this ADR
- `core/ze-communication/ze_communication/types.py::ChannelType` — existing precedent for a
  plugin-facing vocabulary owned outside `core/ze-agents`
</content>
