# Research: Routing Choice After E5 (164)

All unknowns were resolved by the 2026-10-08 Clarifications and by reading the code at `b023dcba`. Items marked **verify at implement** are measured or confirmed against provider docs during implementation; none blocks planning.

## R1 — Choice scope and call frequency

- **Decision**: One batched request on every multi-agent turn when the surface is enabled and calibrated. A single enabled agent keeps the confidence-1 envelope and makes no call (`router.py:_single_agent_envelope`).
- **Rationale**: US1 AC3 wants an honest confidence on clear turns too. Calling only on ambiguous turns would leave clear singles on cosine-as-confidence.
- **Alternative rejected**: Call only below the 160 bars. Cheaper, but confidence stays a cosine on the most common turns.

## R2 — Decision table (`decide`)

Rules run in order over one `SystemOneResult`; rules 1-2 never reach a result.

1. Surface disabled, or `choice_trust`/`multi_specialist_hold` null → no call, 160 path.
2. Fewer than two enabled agents → no call.
3. Result is skip → 160 path (`skip_reason` recorded).
4. Choice answer missing, not a shortlist key or `none`, or `confidence` null → skip `invalid_answer`.
5. Choice `none` (any peakedness) → **decompose**; Choice consumed.
6. Choice agent with peakedness below `choice_trust` → **abstain**: 160 cosine bars decide; Choice unused.
7. Choice agent at or above `choice_trust`:
   - Noul missing → trust (Noul unused);
   - Noul at or above `multi_specialist_hold` → **decompose**; Choice and Noul consumed;
   - otherwise → **trust**; Choice and Noul consumed.

Peakedness below the bar is "unsure", not "none". Treating unsure as abstain keeps 160 as the fallback (spec US2 AC2, FR-006).

## R3 — Disagreement with E5

A trusted Choice agent MAY differ from the E5 top. The Choice is the router's answer in that case (it saw the same shortlist). The disagreement is logged (`routing_choice_disagrees_e5`) so the calibration and eval can count it. The ADR open question 2 ("is *k* too small?") is answered by counting `none` outcomes during calibration.

## R4 — Shortlist

- **Decision**: top-k by cosine, `k = system_one.surfaces.routing.shortlist_k`, default 4, clamped to the enabled agent count. Criteria keys are agent names; values are `@agent.description` stripped. Plus `none`.
- **Rationale**: 160 measured E5 clear tops at 0.78-0.84; k=4 covers a close runner-up without dumping the roster. **Verify at implement** with calibration disagreements; the key lets us retune without code.
- **Option-name bias**: keys are names, descriptions are the criteria text. Production order is E5-rank order (stable per turn); eval shuffles.

## R5 — State sent to System One

- **Decision**: `{"user": <raw user text, capped 2000 chars>, "history": <existing history hint, optional>, "context": <routing_hints, capped 600 chars, optional>}`.
- **Why a signature change**: `embed_route` today concatenates the three into one string for E5 (`nodes/routing.py:48-58`). It keeps doing that for E5, and now also passes the parts separately: `router.route(prompt, session_id, *, judgment_state=...)`. The user text stays the dominant key.
- **Rationale**: pin 6 (minimal state, named fields). The history hint keeps its existing truncation (`_HISTORY_HINT_TURNS`, `_HISTORY_HINT_CHARS`); the caps on `user` and `context` are new and are constants.

## R6 — Complexity Score

- **Decision**: Score with three ordered descriptive levels (`lookup`, `single_tool`, `multi_hop`). Lookup maps to `simple`; `single_tool` and `multi_hop` map to `complex`.
- **Mapping bar**: Score returns a degree, not a label. A third bar `complexity_lookup_max` (null until calibrated) separates lookup from the rest: `score <= bar` → `simple`. When null, the Score is not consumed and the regex runs, for both paths.
- **Where it applies**: the embedding path (router) and the `decompose` node's primary subtask. The router stamps `envelope.complexity_source = "score"`; `decompose` keeps that complexity instead of re-running `classify` when the source is `score`. Subtask models are still resolved with `_resolve_model(agent, complexity)`.
- **Never** picks an agent (US3 AC3).
- **Verify at implement**: the exact wire shape of a Score answer (`answer.score` float range and direction) against the OpenRouter System One docs and the first calibration run.

## R7 — Confidence semantics

- **Decision**: when a Choice is consumed (trust or `none`), `envelope.confidence` = Choice peakedness, `score_gap` stays the cosine gap, `raw_scores` stays cosine. On skip, abstain, or any non-consumed outcome, `confidence` stays cosine.
- **Haiku path**: the envelope returned by `decompose` keeps `confidence = raw_scores.get(primary)` (cosine). Its `routing_method` is `haiku`, so the surface can tell the two meanings apart.
- **Storage**: no `routing_log` migration. `routing_log.method` plus the `messages.trace.judgments` rows disambiguate. No change to the `ComplexityEstimator.classify` `confidence > 0.80` term (regex only runs on skip, where `confidence` is cosine).

## R8 — Production wiring drift (hard cut)

- **Finding**: `bootstrap.build_router` (`bootstrap.py:159`, called by `ze_api/container.py:672`) builds `RouterConfig()` with no `app_config`. The base `Container` (`ze_core/container.py:345-370`) reads YAML `routing:` and `router_fallback` and passes `app_config`. So production ignores `models.overrides` and the router fallback override.
- **Decision**: delete both inline constructions. `ze_core/routing/factory.py` exposes `build_embedding_router(...)`. Both call sites use it. The base `Container` builds a `SystemOneClient` too (it had none). No shim, no second path (Principle VIII).
- **Test**: one test per call site asserts the YAML threshold, `models.overrides[agent]`, `router_fallback` model and the injected client reach the router.

## R9 — Web

- **Decision**: no `[WEB]` task. `JudgmentsSection` (162) renders any `JudgmentTrace`. `RoutingBadge` shows `% conf`; with a consumed Choice that is the peakedness, which is the honest number. The label needs no change.
- **Optional, deferred**: showing `peakedness`/`probabilities` (the `none` probability) in `JudgmentsSection`. Recorded as a follow-up, not scoped. `probabilities` is already on the wire.

## R10 — Eval and calibration

- **Decision**: `eval/calibration/routing.jsonl` (EN+PT; clear singles, close-gap singles, `none`, mixed/sequential, lookup/single-tool/multi-hop complexity labels) and `eval/calibration/routing.py` (opt-in live; shuffles option order; reports Choice vs gold agent accuracy, reliability of peakedness, `none` precision/recall, multi-specialist Noul separation, Score level separation, suggested bars). Roster comes from the checked-in agent descriptions, not a live server.
- **Embedder**: the runner loads the local E5 singleton to build the shortlist, the same `judge.shortlist` helper as the router, so the shortlist is the production shortlist.
- `eval/scenarios/routing.yaml` stays as the end-to-end regression; no new scenario is required because the surface ships off.

## R11 — Cost attribution

`embed_route` sets the telemetry agent context to `router` around the call so System One cost rows are attributed to routing, the same label `decompose` already uses.

## R12 — Retries

`max_attempts=1`. Routing sits on the critical path of every turn; the 162 default (three attempts with 1/2/4 s backoffs) can add seconds. A skip falls through to the 160 path (pin 5).
