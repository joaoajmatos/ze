# Quickstart: Claim Topology

Validation guide for this feature once implemented. No new UI, no new REST endpoint — validation
is at the package/test level plus one live-DB check for the decay bug fix (User Story 1, the
feature's highest-priority scenario).

## Prerequisites

```bash
make db-up
make migrate
```

## 1. Confirm the shared vocabulary has exactly one definition, and `Provenance` stays closed (SC-002)

```bash
grep -rn "class ClaimKind" core/ core/*/ze_*/   # exactly one hit: core/ze-agents/ze_agents/claims.py
grep -rn "class Provenance" core/ core/*/ze_*/  # exactly one hit: core/ze-agents/ze_agents/claims.py
grep -rn "class LoopClaimKind" core/ze-worldstate/  # zero hits — now an alias, not a class
grep -rn "EMAIL\|CALENDAR" core/ze-worldstate/ze_worldstate/types.py  # zero hits — dropped per FR-003
grep -rn "class LoopProvenance" core/ze-worldstate/ze_worldstate/types.py
# expect: a plain class (NOT `class LoopProvenance(StrEnum)`), holding only
# CONVERSATION/INGESTION/USER_DECLARED
```

## 2. Confirm the staleness helper has exactly one implementation (SC-003)

```bash
grep -rn "cutoff = .*now.*- .*timedelta\|now() - (" \
  core/ze-worldstate/ze_worldstate/jobs/ core/ze-automation/ze_automation/jobs/ \
  core/ze-automation/ze_automation/goals/postgres.py core/ze-worldstate/ze_worldstate/store.py
# expect: one hit inside core/ze-proactive/ze_proactive/staleness.py; none of the three sweep
# call sites compute a stale cutoff inline anymore (stuck_goals' unrelated alert_cooldown_days
# suppression predicate is expected to remain — see research.md §7)
```

## 3. Confirm the inflow-channel boundary is unvalidated (plugin-domain-vocabulary.md)

```bash
grep -rn "LoopProvenance(" core/ze-worldstate/ze_worldstate/extraction.py
# expect: zero hits — the ValueError-raising coercion is removed per FR-003
```

```python
# a plugin-style string ze-worldstate has never declared must succeed, not raise
import asyncio
from ze_worldstate.extraction import propose_loop_candidates

async def main():
    loops = await propose_loop_candidates(
        text="Renewed the domain via a future plugin's own sync channel",
        provenance="a_future_plugins_own_channel",  # never declared anywhere in ze-worldstate
        evidence_refs=[],
        llm_client=llm_client, embedder=embedder, loop_store=loop_store,
        entity_resolver=entity_resolver,
    )
    # expect: no ValueError — either [] (conservative gate declines) or a suspected loop,
    # never a raised exception for the unrecognized provenance string

asyncio.run(main())
```

## 4. Run existing test suites unmodified except where retrofit-specific (SC-004)

```bash
make test-worldstate
make test-correlation
make test-memory
make test-plugin
make test-proactive
make test-automation
```

Every pre-existing test should pass unmodified — including the eleven `ze-worldstate` test
files using `LoopProvenance.CONVERSATION`/`LoopProvenance.USER_DECLARED` as loop-construction
fixtures (research.md §3) — since those two symbols still resolve to the same string values.
Only tests added/updated for the new `claim_kind`/`confidence` fields and the decay job should
differ from the pre-feature baseline.

## 5. Prove the frozen-hypothesis-confidence bug is fixed (User Story 1 / SC-001)

The independent test from spec.md, run against a real (migrated) database:

```bash
make dev-eval   # or make dev — either boots the container with the new HypothesisDecayJob wired
```

```python
# one-off script or REPL, using PostgresHypothesisStore directly
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from ze_correlation.types import Hypothesis
from ze_correlation.store import PostgresHypothesisStore
from ze_agents.claims import ClaimKind

async def main():
    store = PostgresHypothesisStore(pool)  # pool from the running container's DI
    h = Hypothesis(
        id=uuid4(), summary="test", narrative="test", relation="pattern",
        confidence=0.8, relevance=0.5, evidence=[], entities=[],
        created_at=datetime.now(timezone.utc) - timedelta(days=31),
        claim_kind=ClaimKind.INFERENCE,
    )
    await store.save(h)
    # run the decay job (directly, or via its proactive-job registration)
    from ze_correlation.jobs.hypothesis_decay import HypothesisDecayJob
    await HypothesisDecayJob(store).run()
    updated = await store.get(h.id)
    assert updated.confidence < 0.8, "confidence did not decay"
    print("confidence after decay:", updated.confidence)  # expect 0.77 (one 30-day period)

asyncio.run(main())
```

**Expected outcome**: `confidence` drops from `0.8` to `0.77` (one `TIME_LINEAR` step,
`-0.03`/30-day period, matching `memory_facts`' reused rate per the clarification), and the
`hypothesis_confidence_decayed` structured log line appears — the auditability bar Acceptance
Scenario 1 requires.

## 6. Confirm a decayed hypothesis drops out of push eligibility (Acceptance Scenario 2)

```python
from ze_correlation.push import passes_confidence
assert not passes_confidence(updated.confidence, tau=0.6)  # matches config's tau_push default
```

## 7. Confirm zero unclassified rows post-migration (SC-006)

```sql
SELECT count(*) FROM correlation_hypothesis WHERE claim_kind IS NULL;  -- expect 0
SELECT count(*) FROM memory_facts WHERE claim_kind IS NULL;            -- expect 0
```

## 8. Lint and type-check

```bash
make lint
```
</content>
