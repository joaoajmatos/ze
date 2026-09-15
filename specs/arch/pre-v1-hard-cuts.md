# ADR: Pre-v1 Hard Cuts — No Compatibility Until v1

> **Status:** Accepted
> **Date:** 2026-09-15
> **Scope:** All packages, all stores, all public APIs, all migrations.
> **Amends:** `.specify/memory/constitution.md` Principle VIII (v1.2.0).
> **Constrains:** every subsequent spec and ADR until a versioned v1 is declared,
> including the remaining contribution-seam work in
> [`contribution-seam.md`](contribution-seam.md).

---

## Context and Problem Statement

Ze has never been deployed. There is no production database, no external plugin
author, and no released client that must keep working. Even so, several write
paths grew a wrap-then-replace habit: a new contract (`Contribution`,
`submit_and_detect_collisions`) sits beside the old store method
(`MemoryStore.propose_facts()`), and the old method stays public so existing
callers do not break.

That habit is the wrong default before v1. It leaves two ways to mutate the
world-state, only one of which is licensed. It also trains later specs to treat
"don't break the current API" as a constraint that does not exist yet.

The question is whether pre-v1 work must preserve call signatures, schemas, and
on-disk rows, or whether the correct move is to delete the old path.

---

## Decision Drivers

- Constitution Principle I (spec-first) already forces intent to be written down;
  it does not require the previous intent to remain callable.
- Doctrine (`ze-doctrine.md`) wants one proposal seam, not a seam plus a back
  door. A compatibility overlay is a second seam.
- Dev data is disposable (`ze-seed` already wipes and reseeds the `seed-dev-*`
  namespace). Schema rewrites are cheaper than dual vocabularies.
- v1 is a real future event. Compatibility becomes a duty then, not now.
  Recording the expiry in the constitution stops this principle from silently
  surviving the first release.

---

## Considered Options

1. **Preserve call signatures until v1** — wrap new contracts around old
   methods; keep deprecated aliases; migrate data in place with dual-read.
2. **Hard-cut until v1** — delete or reshape the old path in the same phase that
   introduces the new one. Wipe and remigrate local databases. No shim except
   what a single in-flight phase needs internally, deleted before that phase
   closes.
3. **Case-by-case** — allow shims when a refactor feels large. Rejected: this is
   how `propose_facts()` survived next to the contribution seam.

---

## Decision Outcome

**Chosen option: Hard-cut until v1 (Option 2).**

Until a versioned v1 release is declared:

- A spec MAY break Python APIs, REST paths, WebSocket frames, dataclass fields,
  and Postgres columns.
- A spec MUST NOT add a compatibility shim, deprecated alias, dual-write, or
  dual-read "so existing callers keep working." In-tree callers are updated in
  the same phase.
- A spec MUST NOT keep a second vocabulary for the same concept (for example
  `Fact.provenance: str` of `"raw"` / `"synthesized"` beside
  `ze_agents.claims.Provenance`) in order to avoid a migration.
- Alembic migrations MAY drop columns and rewrite types. Local and seed
  databases are expected to be destroyed and recreated. There is no production
  cutover to design.
- Wrap-then-replace is forbidden as a *multi-phase* strategy. A phase may wrap
  for a few commits while call sites move; the old public entry point MUST be
  gone when the phase's spec status flips to Done.

At v1, this ADR is superseded by a new compatibility ADR and Principle VIII is
amended in the same commit. Until that commit, "backward compatible" is not a
valid objection to a spec.

### Positive Consequences

- The remaining contribution-seam work can make `propose_facts()` a private
  write callback instead of a public ungated API.
- Agents and contributors default to the shape the doctrine wants, not the
  shape last week's caller used.
- v1 starts from one write path per kind of claim, not a museum of adapters.

### Negative Consequences / Trade-offs

- Local databases will not survive some phases. That is accepted.
- In-progress branches that imported a deleted symbol must rebase. That is
  accepted.
- After v1 this default reverses, and later specs will pay for the cuts we make
  now. That is the point of having a v1 declaration at all.

---

## What this does not license

Hard-cuts are for **wrong or duplicate contracts**, not for skipping the
doctrine's other gates:

- Cross-function **arbitration** stays gated on collision evidence
  (`contribution-seam.md` step 8). Undeployed status does not invent an arbiter.
- Loop and goal **stores stay un-unified** (Phase 110 FR-014) unless a later
  spec argues for the merge on its own merits.
- Spec-first (Principle I) still applies. A hard-cut is still a specced change.

---

## Relationship to the spine write-path roadmap

The first application of this ADR is the remaining contribution-seam work:
perception facts on the seam, then a hard-cut of `memory_facts` onto the shared
claim vocabulary. Sequencing lives in [`contribution-seam.md`](contribution-seam.md)
§Phased rollout. Those phases MUST delete the ungated `propose_facts()` door
rather than wrap it.
