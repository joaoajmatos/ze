# Quickstart: Validating Social Cognition Co-Occurrence

Prerequisites: `make db-up && make migrate` (applies `zcor003`). Fixtures need
at least one `person` and one `project` entity already in the memory graph
(seed via `make seed` or a short conversation that mentions them once, so
Phase 128's extraction creates the entities — this phase never creates a
project entity that doesn't already exist, per its Edge Cases).

## 1. Hedged belief from reply-and-meeting co-occurrence (User Story 1 / SC-001)

```bash
# Seed 2+ distinct events (a reply-thread email, a calendar meeting) inside
# the last 30 days mentioning both a known person and a known project as an
# actual participant (not only CC'd), then run the job directly:
python -c "
import asyncio
from ze_personal.jobs.social_cooccurrence import SocialCooccurrenceJob
asyncio.run(SocialCooccurrenceJob(...).run())
"

# Ask Ze conversationally: "who seems to be on Launch?"
# Expect a hedged answer citing at least one piece of evidence, and:
```

```bash
curl -s -H "Authorization: Bearer $ZE_API_KEY" \
  http://localhost:8000/api/v0/memory/graph?entity=Launch | jq '.relationships'
# -> no WORKS_ON edge yet (still just the hypothesis)
```

## 2. Corroboration promotes to a real edge (User Story 2 / SC-002)

```bash
# Re-run the job after evidence spans 2 distinct events on 2 distinct days
# (Decision 3's gate) — or call the confirm tool directly:
#   confirm_project_membership(<hypothesis_id>)

curl -s -H "Authorization: Bearer $ZE_API_KEY" \
  http://localhost:8000/api/v0/memory/graph?entity=Launch | jq '.relationships'
# -> WORKS_ON edge now present, provenance=synthesized

# A second person only ever CC'd (never corroborated, never confirmed):
# confirm the graph query for that person's edge still returns nothing.
```

## 3. CC-only broadcast never promotes (User Story 3a / SC-003)

```bash
# Seed a single CC-heavy email (many recipients, zero replies) naming a
# project, run the job:
# -> 0 hypotheses reach promotion; querying the graph for any of those
#    recipients' WORKS_ON edge to that project returns nothing.
# -> Asking "who is on Launch?" does NOT list the CC'd recipients.
```

## 4. Aged-out membership drops from current view without closing the project (User Story 3b / SC-004)

```bash
# Take a promoted WORKS_ON edge, backdate its last_contact past 30 days
# (or wait), then:
curl -s -H "Authorization: Bearer $ZE_API_KEY" \
  http://localhost:8000/api/v0/memory/graph?entity=Launch | jq '.relationships'
# -> the aged-out person's edge is either omitted from a "current members"
#    filtered view, or present with a visibly stale last_contact if the
#    query returns raw edges — the project entity itself is still queryable
#    and carries no active/closed field.
```

## 5. Unconfirmed inference never spends the shared attention budget (SC-005)

```bash
# With one unconfirmed co-occurrence hypothesis and one real drifting loop
# both eligible on the same day, inspect push_log after the daily sweep:
psql $DATABASE_URL -c "select source_kind, source_id from push_log where sent_at::date = now()::date;"
# -> the drifting loop may appear; no row with source_kind referencing this
#    phase's hypothesis ever appears — list_stale_for_follow_up continues to
#    rank only confirmed/extracted relationships (FR-010).
```

## Test suite

```bash
make test-ze-correlation   # store: confirm(), mark_promoted(), list_by_entities()
make test-ze-personal      # scoring, corroboration gate, job, tools, seam promotion
make test-ze-sdk           # ze_sdk.correlation re-export smoke test, if added
```

All must pass, plus `make lint`, before this phase is considered done
(Constitution V).
