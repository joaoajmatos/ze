# Implementation Plan: Loop Confirmation Path

**Branch**: `171-loop-confirmation` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/171-loop-confirmation/spec.md` (six user answers recorded 2026-10-12). Governing: [`executive-function.md`](../../arch/executive-function.md) F2, F10, §8 D2.

## Dependencies and merge order

| Phase | State on 2026-10-12 | What 171 needs from it | Rule |
|---|---|---|---|
| **169** loop track tool | Implemented on its floor, not on `main` | `LoopStore.stamp_declared`, `DECLARED_CONFIDENCE` (`ze_worldstate/types.py`), `track_loop_succeeded` + `strip_track_claims` + `COULD_NOT_TRACK` (`ze_agents/nested_tools.py`), `LoopsAgent` with `track_loop` and its instructions, `eval/scenarios/loops.yaml` | **Hard.** 171 implementation starts after 169 is on `main`. T001 re-reads the 169 diff. |
| **170** executive repair | Specced, "starts after 169 lands" | Deadline-only `list_drift_candidates` (so a confirmed loop actually drifts); `apps/ze-api/tests/pg/` harness and `@pytest.mark.pg`; evidence on gate-created loops (the page shows real provenance) | **Hard.** 171 implementation starts after 170 is on `main`. T001 re-reads the 170 diff. 171 edits no file 170 owns except adding one new module under `apps/ze-api/tests/pg/`. |
| **172** corroboration | Being specced (Tern); plans migration `zw003` | Nothing | 171 adds **no** `zw` migration (confirmed to Tern 2026-10-12). When 172 raises suspected confidence, the offer order follows with no 171 change. |

Merge order: **169 → 170 → 171**. If 170 slips, 171 could land after 169 alone only by dropping the pg test (T032) and accepting that confirmed loops do not drift until 170. That is the Maestro's call, not the default.

## Summary

1. **Page** (`ze-web`): new page slice `pages/loops` mounting `LoopReviewList` at `/loops` ("Open loops", Automation group after Priority). The widget groups loops into "Needs your OK" (suspected) and "Tracking" (active, drifting), with Keep on suspected rows.
2. **One confirm**: `review.confirm_loop` = `transition(suspected→active)` + 169's `stamp_declared(confidence=0.9, deadline=now+7d)`. REST and the page get it for free.
3. **Chat confirm**: `confirm_loop(loop_id)` WRITE tool on the loops agent; 169's `track_loop_succeeded` becomes `tracking_earned` and also counts a successful `confirm_loop`.
4. **Resume offer**: `TurnSurfacing.resume_loop_offers(limit=3)` selects suspected loops not offered in 168 h and logs `worldstate_loop_offer:<id>` in `push_log`; `ResumeRecap` renders a "Not yet tracked" block plus the ask instruction; `fetch_context` returns `loop_offer_ids`, carried onto `MessageTrace`.
5. **"What's open"**: `ze_priority/open_query.py` `OpenQueryDetector` (E5 cosine against EN + PT examples, threshold from offline calibration); `fetch_context` computes `open_items_query` once from the prompt embedding it already has; `surface_loops` reads the flag. Regex deleted.
6. **Caps**: `recap_mentions(limit)`; recap 5, explicit 10.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript + React (ze-web).

**Primary Dependencies**: Existing only. `ze-priority` already depends on `ze-worldstate` and `ze-proactive`. The embedder reaches `TurnSurfacing` as a constructor argument typed `Any` (duck-typed `encode`), so `ze-priority` gains no `ze-core` edge.

**Storage**: No migration. `push_log` (`zpro`) rows with `event_type = 'worldstate_loop_offer:<uuid>'` via `PushLogStore.log` / `was_sent_within_hours`. `open_loops` columns as written by 169's `stamp_declared`.

**Testing**: pytest (`AsyncMock` stores, fake embedder with fixed vectors), `@pytest.mark.slow` for the real-E5 held-out check, `@pytest.mark.pg` for the real-Postgres confirm/offer test (170 harness), vitest for ze-web. Gates: `make test-worldstate test-priority test-core test-agents test lint test-web typecheck-web`, `make test-pg`, `make calibrate-open-query`.

**Constraints**:
- `ze_core` never imports `ze_priority` or `ze_worldstate`; it calls the surfacer duck-typed through `config["configurable"]["turn_surfacer"]` (unchanged pattern).
- Pre-v1 hard cuts: `is_global_open_query(prompt)` → `is_global_open_query(embedding)`, `track_loop_succeeded` → `tracking_earned`, `_GLOBAL_OPEN_RE` deleted; all callers and test doubles updated in the same change.
- ze-web FSD: `pages/loops` imports `widgets/loop-review`; the widget imports `entities/loop`; nav route in `shared/config/nav-routes.ts` plus a lazy entry in `app/router/routes.ts`.
- Doctrine functions served: **Executive function** (open-loop state, attention) and **Reflection** (honesty guard on tracking claims). Agency: the user sees, confirms and refuses every inferred loop.

**Performance**: detection adds one cosine over about 30 cached vectors per turn (no model call); offers add one `open_loops` read and at most one push-log lookup per suspected loop, on resume turns only.

## Constitution Check

| Principle | Status |
|---|---|
| I Spec-first | Pass: this spec, user answers recorded. |
| II Single user | Pass: no per-user keys; one push-log namespace. |
| III Layered packages | Pass: changes stay in `ze-worldstate` (review, tools, agent), `ze-priority` (turn, open_query, types), `ze-agents` (nested_tools), `ze-core` (context, loop_surfacing, memory, state, trace, message types/store), `ze-api` (container, schemas, messages route). No new package edge. |
| IV Typed Python | Pass: `LoopOffer` dataclass in `ze_priority/types.py`; no Pydantic outside `schemas.py`. |
| V Tests | Pass: fail-first unit tests per FR; real-Postgres and real-E5 tests for the two places where mocks have hidden defects before (the F1 lesson). |
| VI Explicit persistence | Pass: no migration; existing `push_log`. |
| VII One gateway, local embeddings | Pass: detection uses the local E5; no new LLM call. |
| VIII Hard cuts | Pass: renamed and deleted symbols, no shims. |

Post-design re-check: unchanged.

## Blast radius (graphify affected, depth 2, plus grep for duck-typed callers; this floor, 2026-10-12)

| Symbol | Dependents | Action |
|---|---|---|
| `TurnSurfacing` (ctor, `is_global_open_query`, `recap_mentions`, new `resume_loop_offers`) | `ze_api/container.py:515` (only constructor), `apps/ze-api/tests/api/test_workspace_followthrough.py` (`_real_push_stack`), `ze_priority/__init__.py`, `tests/test_turn.py`; duck-typed: `ze_core/.../nodes/context.py:70,100,104`, `nodes/loop_surfacing.py:19`; doubles in `ze-core/tests/orchestration/nodes/test_context.py:72-76`, `test_loop_surfacing.py:51,119` | Ctor gains a required `embedder`; update the container and the followthrough helper; update every double. |
| `ResumeRecap`, `_assemble_resume_recap`, `fetch_context` | `nodes/test_context.py`, `test_context_continuity_composition.py`, `test_nodes.py`, `test_procedure_discovery.py`, `nodes/__init__.py` | Add the field and render block; return two new state keys; existing rendered-text assertions keep passing (the block is appended after "Still open" and workflows). |
| `surface_loops` | `test_loop_surfacing.py`, `nodes/test_context.py:253`, graph | Reads `state["open_items_query"]`; the `is_global_open_query` doubles leave its tests. |
| `review.confirm_loop` | `rest.confirm_loop` → `ze_api/api/routes/loops.py:59`, `tests/test_review.py:30`; new caller `agents/tools.py:confirm_loop` | Add `stamp_declared`; fake stores in worldstate tests must implement it (169 already added it to the Protocol). |
| `track_loop_succeeded` (169) | `ze_agents/nested_tools.py`, `ze_core/orchestration/nodes/memory.py` (gate skip), `ze-agents/tests/test_track_loop_honesty.py`, `ze-core/tests/orchestration/test_loop_admission_node.py` | Rename to `tracking_earned` and count `confirm_loop` too. **Gate-skip consequence:** `write_memory` also skips the 168 gate after a successful `confirm_loop`. Intended: the user just answered about loops, and the gate would read "yes keep the bank one" as a fresh declaration. Tests updated. |
| `AgentState`, `MessageTrace`, `MessageTraceResponse` | trace node, message store parser, `ze_api/api/messages.py:117`, generated `packages/ze-client` types | Add `loop_offer_ids` along the `resume_recap_applied` path; run `make codegen`. |
| `navRoutes` / `automationNavRoutes` | `AppShell.tsx`, `nav-routes.test.ts`, `app/router/routes.ts` | Add `loops`; extend the automation filter; add the lazy entry. |

Boundary checks for reviewers: `graphify path "ze_priority.open_query" "ze_core"` → no path; `rtk proxy grep -rnE "^(from|import) ze_(priority|worldstate)" core/engine/ze-core/ze_core` → empty.

## Design

Decisions and rejected alternatives: [research.md](research.md). Types and state: [data-model.md](data-model.md). Interfaces: [contracts/confirm-and-offer.md](contracts/confirm-and-offer.md), [contracts/open-query.md](contracts/open-query.md). Commands: [quickstart.md](quickstart.md).

### Turn sequence in `fetch_context` (normative)

1. `prompt_embedding = embedder.encode(embed_text)` (unchanged).
2. `open_items_query = surfacer.is_global_open_query(prompt_embedding)` when a surfacer exists, else `False`; any exception → `False` with a warning.
3. On the gap branch, `_assemble_resume_recap(session_id, config, gap_minutes)`:
   - `recap_mentions(limit=RECAP_LIMIT)` → `open_item_lines`;
   - unless `config["configurable"].get("retry_mode")`: `resume_loop_offers()` → `loop_offers` (exception → `[]`);
   - `ResumeRecap(..., loop_offers=...)`; `has_content()` counts offers.
4. When `open_items_query`: `_open_priorities_note(config)` uses `recap_mentions(limit=OPEN_QUERY_LIMIT)`.
5. The node returns `open_items_query` and `loop_offer_ids = [str(o.loop_id) for o in offers]`, always present (`[]` off the gap branch), so a checkpointed value from an earlier turn never leaks.
6. `surface_loops` returns `{}` when `state.get("open_items_query")` is true.
7. `record_trace` copies `loop_offer_ids` onto `MessageTrace`.

### Files touched

```text
core/cognition/ze-worldstate/ze_worldstate/
├── review.py                  # confirm_loop stamps 0.9 + deadline
├── agents/tools.py            # + confirm_loop tool
└── agents/agent.py            # tools, intent text, description, routing_criteria, instructions
core/cognition/ze-worldstate/tests/{test_review.py, test_confirm_loop_tool.py (new), test_loop_agent_cancel.py}
core/contracts/ze-agents/ze_agents/nested_tools.py   # tracking_earned
core/contracts/ze-agents/tests/test_track_loop_honesty.py
core/arbitration/ze-priority/ze_priority/
├── open_query.py              # new: OpenQueryDetector, examples, OPEN_QUERY_THRESHOLD
├── turn.py                    # embedder arg, is_global_open_query(embedding), recap_mentions(limit), resume_loop_offers
├── types.py                   # + LoopOffer
└── __init__.py                # exports
core/arbitration/ze-priority/tests/{test_turn.py, test_open_query.py (new), test_open_query_holdout.py (new, slow)}
core/engine/ze-core/ze_core/orchestration/
├── nodes/context.py           # ResumeRecap.loop_offers, caps, open_items_query, loop_offer_ids
├── nodes/loop_surfacing.py    # read the state flag
├── nodes/memory.py            # call tracking_earned
├── nodes/trace.py             # loop_offer_ids
└── state.py                   # open_items_query, loop_offer_ids
core/engine/ze-core/ze_core/conversation/messages/{types.py, store.py}
core/engine/ze-core/tests/orchestration/{nodes/test_context.py, nodes/test_loop_surfacing.py, test_loop_admission_node.py, nodes/test_trace*.py}
apps/ze-api/ze_api/{container.py, api/schemas.py, api/messages.py}
apps/ze-api/tests/{api/test_workspace_followthrough.py, api/test_loops*.py, pg/test_loop_confirmation_pg.py (new)}
packages/ze-client/src/generated/*   # make codegen
apps/ze-web/src/
├── pages/loops/{index.ts, ui/LoopsPage.tsx, ui/LoopsPage.test.tsx}   # new
├── widgets/loop-review/ui/{LoopReviewList.tsx, LoopReviewList.test.tsx}
├── shared/config/{nav-routes.ts, nav-routes.test.ts}
└── app/router/routes.ts
eval/calibration/{open_query.jsonl, open_query_holdout.jsonl, open_query.py}   # new
eval/calibration/routing.jsonl          # + 4 training rows
eval/scenarios/loops.yaml               # + 2 scenarios (file created by 169)
Makefile                                 # calibrate-open-query
docs: README.md, docs/architecture.md, docs/cognitive-architecture.md, docs/eval.md, docs/testing.md,
      core/arbitration/ze-priority/README.md, core/cognition/ze-worldstate/README.md, apps/ze-web/README.md (if it lists pages)
```

## Lanes (summary; the full list is in tasks.md)

- **ENG** (Sonnet, lead): confirm semantics, honesty rename, offers, recap, detector, calibration, trace path, container, pg test, integration and gates.
- **JR-web** (flash): page slice, widget grouping, nav and router, vitest.
- **JR-docs** (flash or Docs Steward): docs and the coverage check, after the ENG code is merged.

## Complexity Tracking

No constitution violations.
