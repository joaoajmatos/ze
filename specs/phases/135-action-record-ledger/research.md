# Research: Action Record Ledger

## R1. Ledger ownership and authoritative records

**Decision:** `ze-memory` owns the append-only cross-domain ledger; each row points to exactly
one plugin/core-owned `AuthoritativeRef(domain, record_id)`.

**Rationale:** The ledger is evidence across domains, while workspace, messenger, calendar, and
automation retain their detailed operational truth. Duplicating their schemas in `ze-memory`
would create a competing truth and coupling to plugin vocabulary.

**Rejected:** One table per plugin (not cross-domain); replacing source stores (wrong ownership);
using `memory_facts` (an ActionRecord is evidence of execution, not a user claim).

## R2. Minimum doctrine hard cut

**Decision:** Add `ClaimKind.ACTION_RECORD` to the closed shared vocabulary and license it only
to `SourceFunction.ACTION`. Remove ACTION's empty license in the same change. The new kind is
not a fact, inference, suspicion, identity, or priority.

**Rationale:** Doctrine permits Action to record what it did, yet the current license makes
Action unable to submit any contribution. A distinct kind preserves the rule that Action does
not create general claims about user intent or the world.

**Rejected:** License ACTION for `FACT` (would turn action outcomes into truth claims);
reuse `FACT` with a flag (weakens claim-kind semantics); add arbitrary action-domain enum values
to doctrine (plugin vocabulary belongs in `AuthoritativeRef.domain`).

## R3. Append-only lifecycle observations

**Decision:** Each row is an immutable observation with a lifecycle state. A started action, a
completion, a retry, and a correction may be separate records. `retry_of` and `supersedes`
express history; no row is updated to a later state.

**Rationale:** A mutable status row loses the evidence that a side effect was attempted and makes
failure investigation unreliable. Immutable records retain a truthful audit trail.

**Rejected:** One mutable status record (history loss); database update plus history table
(two representations of the same ledger).

## R4. Idempotency boundary

**Decision:** `idempotency_key` identifies one logical action observation, and is unique in
`action_records`. Concurrent inserts use database conflict handling to return the prior record.
A retry/correction deliberately uses a new key and cites its predecessor.

**Rationale:** Delivery callbacks are at-least-once. Database-enforced uniqueness is the only
cross-process guarantee; in-memory dedup is insufficient.

**Rejected:** Dedup by summary or timestamps (ambiguous); one key across retries (suppresses real
attempts); rely only on a source domain's idempotency (does not cover all producers).

## R5. Failure and handoff semantics

**Decision:** The authoritative domain action commits according to its existing transaction
model. Ledger append is a separate, recoverable handoff: an append failure is surfaced and
retried using the same idempotency key, without repeating the side effect. Terminal result states
are explicit; inability to determine an outcome is `unknown`.

**Rationale:** Cross-package distributed transactions are unavailable and would make the ledger
own domain behavior. Silent drop is unacceptable evidence loss; fabricated failure/success is
worse.

**Rejected:** Roll back a completed domain action when ledger write fails (unsafe/impossible);
rerun action automatically (may duplicate side effects); mark success on callback receipt.

## R6. Evidence and causality

**Decision:** `Contribution.evidence` gains action-record references alongside existing stable
spine evidence. `ActionRecord` separately carries `causal_refs` for initiating/authorizing
context and optional `retry_of`/`supersedes` action-record ids. Existing dangling checks remain
strict where a checker exists; action-record citation receives a store-backed checker.

**Rationale:** Evidence asks “what supports this observation”; causality asks “what caused or
changed this action.” Keeping both makes provenance inspectable without treating an action record
as a fact.

**Rejected:** Free-text causal history (not queryable); overloaded `source_refs` (Fact-specific);
skip validation universally (allows broken audit chains).

## R7. Initial producers

**Decision:** Start with `ze-workspace` runs and one messenger outbound send as reference
producers. Their existing persisted run/sent-message records become `AuthoritativeRef`s. The
contract accommodates calendar, workflow, and goal actions later.

**Rationale:** These demonstrate local execution and remote communication without binding the
ledger to a single domain. Both have meaningful failure modes and durable records.

**Rejected:** Migrate every tool at once (large, unverifiable); record only workspace (not
cross-domain); instrument raw LLM tool-call traces (not authoritative execution evidence).

## R8. Explicit non-decisions

Collision detection may log ActionRecord conflicts only if the existing seam can do so without
new policy. This feature does **not** decide whether competing records are arbitrated, how an
arbiter chooses a winner, or how `signal_sources()` changes delivery. Those remain separate
contribution-seam roadmap work.
