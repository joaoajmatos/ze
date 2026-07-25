# Quickstart: Validating Open-Loop Drift Detection & Surfacing

Prerequisites: `make db-up`, `make migrate` (after `zw002_drift_columns.py` lands), `make dev`
(backend on `:8000`). A Phase A `active` loop must already exist as a starting point for most
scenarios below — see Phase 109's own quickstart §1–2 to create one.

Each scenario maps to a User Story / Success Criterion in `spec.md`.

## 1. A stalling loop drifts on schedule (User Story 1, SC-001, SC-002)

Create an `active` loop with an implied timeframe that has already elapsed (or set
`worldstate.drift.window_days: 0` in a dev config override so any confirmed loop is
immediately eligible), then invoke the sweep directly rather than waiting for its cron:

```bash
# via a dev/test shell — DriftSweepJob.run() is a plain proactive_job, callable directly:
python -c "
import asyncio
from ze_worldstate.jobs.drift_sweep import DriftSweepJob
# construct with the same loop_store the running app uses, then:
asyncio.run(DriftSweepJob(loop_store=...).run())
"

curl localhost:8000/api/v0/loops/{loop_id} -H "Authorization: Bearer $ZE_API_KEY"
```

**Expected**: `"state": "drifting"`, `"drift_rationale"` present and phrased as an observation
("no corroborating evidence since confirmation..."), never a verdict. No push and no WS/ntfy
notification was sent as a side effect of the sweep itself (check `GET /api/v0/notifications`
is unaffected).

Repeat with fresh evidence linked since confirmation (e.g. mention the same topic again in a
way that re-links evidence) — **expected**: the loop remains `active` after the sweep.

## 2. Contradiction drifts a loop immediately (User Story 1, Acceptance Scenario 3)

With an `active` loop whose evidence is a fact later contradicted (via the existing memory
consolidation contradiction path, same one exercised by Phase 109 quickstart's "Evidence
retraction cascade" scenario):

```bash
curl localhost:8000/api/v0/loops/{loop_id} -H "Authorization: Bearer $ZE_API_KEY"
```

**Expected**: `"state": "drifting"` immediately after the contradiction is written — no sweep
invocation needed — with `drift_rationale` citing the specific contradicting evidence.

## 3. Inline mention on topical overlap (User Story 2, SC-004)

With a `drifting` loop linked to an entity (e.g. "Maria"), send a turn referencing that entity:

```bash
curl -X POST localhost:8000/api/v0/messages -H "Authorization: Bearer $ZE_API_KEY" \
  -d '{"text": "What has Maria been up to lately?"}'
```

**Expected**: the response includes a hedged mention of the drifting loop ("it looks like...")
with evidence available in the response's `components` (a `type: "drifting_loop"`-shaped entry
alongside any `type: "connections"` correlation component, if one is also present). Send an
unrelated turn ("what's the weather") — **expected**: no loop mention appears, and `GET
/api/v0/loops` shows no state change (inline never mutates loop state).

Repeat the Maria-referencing turn again — **expected**: the loop may be mentioned again (no
novelty/budget gate on inline, FR-006/SC-004's counterpart on the "no false positive" side is
about *unrelated* turns, not repeated relevant ones).

## 4. High-confidence drifting loop earns a push (User Story 3, SC-003, SC-006)

Seed a `drifting` loop whose confidence, relevance, and grounded evidence all clear the
configured push thresholds (`config.yaml`'s `worldstate.push.tau_push` /
`tau_relevance` / grounding), with the daily open-loop push budget not yet exhausted, then
invoke the push sweep directly (same pattern as scenario 1):

```bash
curl localhost:8000/api/v0/notifications -H "Authorization: Bearer $ZE_API_KEY"
```

**Expected**: exactly one new notification, phrased as a hedged nudge, and a `push_log` row
under `event_type = "worldstate_loop_push"`. Re-run the push sweep immediately — **expected**:
no second push (novelty window). Exhaust the sibling budget (repeat with enough qualifying
loops, or lower `max_pushes_per_day` in a dev config override) — **expected**: a further
qualifying loop is not pushed until the budget window resets, while `GET
/api/v0/notifications` for the **correlation engine's own** pushes (if any fired in the same
window) is unaffected — proving the budgets are independent (Clarification).

## 5. Push safety checks (Edge Cases, FR-011, FR-012)

- **Race with user action**: seed a qualifying `drifting` loop, close it via
  `POST /api/v0/loops/{id}/close` immediately before the push sweep runs (or between sweep
  selection and send, if testing at the unit level with a mocked delay) — **expected**: no push
  is sent; the sweep's immediate re-check (FR-011) catches the closed state.
- **Inline-then-push cooldown**: trigger scenario 3's inline mention for a loop, then
  immediately run the push sweep for that same loop even though it otherwise clears the bar —
  **expected**: no push within the cooldown window (FR-012); re-run the sweep after the
  cooldown elapses — **expected**: it may now push if still qualifying.
- **Grounding failure**: contradict the loop's cited evidence after it drifted but before the
  push sweep runs — **expected**: no push (the grounding check re-evaluates at push time, not
  drift time).
- **Untouched non-active states**: seed one loop each in `suspected`, `closed`, `dropped`; run
  the drift sweep — **expected**: none of them change state (FR-004).

## Automated coverage

Each scenario above should have a corresponding test: `core/ze-worldstate/tests/test_drift.py`
and `tests/jobs/test_drift_sweep.py` (scenarios 1, 2, 5's last bullet), `test_surfacing.py`
(scenario 3, and the push-bar/cooldown logic in `tests/jobs/test_push_sweep.py`, scenarios 4–5),
plus `core/ze-correlation/tests/test_push.py` extended to confirm the extracted bar functions
are behavior-preserving. A new `core/ze-core/tests/` node test covers the `surface_loops`
node's `config["configurable"]` contract (present/absent `loop_surfacer`, matching how
`nodes/correlation.py` is tested).
