# CF-02 — E5 embedding calls and render tools

> **Status:** Design note for floor CF-02 (cleanup report 2026-10: S-01, R-03, U-01).
> **Date:** 2026-10-16
> **Base:** `main` @ `948bdfdf`
> **Scope:** `ze_core/embeddings.py` and every `encode(...)` caller; the open-query detector; the memory relevance floor; the companion's `tools` list.
> Pre-v1: hard cut, no alias for `encode()`.

## 1. Problem

`E5Embedder.encode()` is a "compat shim" that prefixes every input with `passage:`. Ten callers use it. Two of them embed a **user question** that is then matched against stored content: `fetch_context` (retrieval query) and the tool executor's `embed_fn` (retrieval query). E5 is asymmetric: a question wants `query:`, stored content wants `passage:`. Today those retrievals run passage-versus-passage.

`encode()` also hides intent. A reader cannot tell whether a call site embeds a question, stored text, or one side of a dedup comparison.

## 2. Decision

Delete `E5Embedder.encode()`. Every caller picks `encode_query` or `encode_passage`. No alias, no default.

**Rule for choosing.**

| Situation | Method | Why |
|---|---|---|
| Text that is **stored** (fact value, episode, summary, entity name, event title, procedure trigger, seed row) | `encode_passage` | E5's own prefix for stored content. Stored vectors are already passage vectors, so no re-embedding migration. |
| A **user question or prompt matched against stored content** (retrieval) | `encode_query` | The asymmetric case E5 is trained for. |
| **Symmetric comparison of two texts of the same kind** (loop title vs loop title, fact vs fact, merchant vs merchant, forget phrase vs fact value, item description vs item title) | `encode_passage` on both sides | Scores stay identical to today, so every threshold calibrated on them stays valid. Only the retrieval path moves. |
| Rank-only retrieval check with no threshold (dream gate 3) | `encode_query` | The content is the query. Rank order only, nothing to recalibrate. |

`encode_query` takes one string, `encode_passage` takes a string or a list. Batched sites (`consolidator`, `detector`, `open_query`) use `encode_passage`, which already batches.

### Call sites

| Site | Method | Threshold affected |
|---|---|---|
| `ze_core/orchestration/nodes/context.py` retrieval `prompt_embedding` | `encode_query` | relevance floor, composite similarity term (§3.2) |
| same node, open-query vector | `encode_passage` (second call) | open-query threshold (§3.1) |
| `ze_core/orchestration/nodes/execution.py` `_embed_fn` | `encode_query` | relevance floor (§3.2) |
| `ze_core/orchestration/nodes/memory.py` episode embedding | `encode_passage` | none (stored) |
| `ze_memory/retriever.py` `_select_forget_match_ids` | `encode_passage` | forget 0.88 / 0.80 unchanged (§3.3) |
| `ze_memory/retriever.py` event title, entity name, fact value | `encode_passage` | none (stored) |
| `ze_memory/consolidator.py` (3), `session_summary.py`, `dream/promoter.py`, `procedures/store.py` | `encode_passage` | none (stored / dedup) |
| `ze_memory/dream/gates.py` gate 2 (novelty vs stored facts) | `encode_passage` | novelty threshold unchanged |
| `ze_memory/dream/gates.py` gate 3 (retrievability, top-k by rank) | `encode_query` | none (rank only) |
| `ze_worldstate/matching.py`, `ze_correlation/push.py` | `encode_passage` both sides | none |
| `ze_priority/tools.py` `_disambiguate` | `encode_passage` both sides | `_MATCH_FLOOR` 0.55 / margin 0.05 unchanged |
| `ze_priority/open_query.py` examples | `encode_passage` | §3.1 |
| `ze_seed/domains/_helpers.py`, `ze_messenger/inbound/processor.py` | `encode_passage` | none (stored) |
| `ze_finance/recurring/detector.py` (`TextEmbedder` Protocol) | `encode_passage` | merchant merge threshold unchanged |
| `eval/calibration/{open_query,corroboration}.py` | match production | — |

Some of these files belong to other floors (`ze_priority/tools.py`, `ze_seed`, `ze_messenger`, `ze_finance`, `execution.py`, `memory.py`). The edit is one line each and follows from deleting the method. No other change is made in them.

## 3. Calibration

All numbers come from the local `intfloat/multilingual-e5-base` model. Nothing here spent credits.

### 3.1 Open-query detector (R-03)

The detector compares the turn's prompt vector to embedded example questions, subtracts a Portuguese offset, and fires at `max >= 0.88`. Four encodings were compared on the four labeled sets (tuned 88 rows, held-out 1 and 2 as before, plus a new held-out 3 of 48 rows). Selection rule: highest mean recall subject to **zero false positives on every set**, because a false positive is the costly error (171 research.md).

| Prompt / examples | Best offset, threshold | Mean recall at zero FPR |
|---|---|---|
| passage / passage (today) | 0.05, 0.8775 | **0.79** |
| query / query | 0.01, 0.8825 | 0.69 |
| query / passage (what a naive swap gives) | — | collapses (EN recall 0.32 at 0.88) |

The shipped constants are already at the optimum for passage/passage: threshold 0.88, offset 0.05 (0.8775 is the bound, 0.88 sits inside the same zero-FPR region). Query/query loses about ten points of recall at equal FPR, and held-out 2 Portuguese would drop from 0.667 to about 0.58, under the amended bar of 0.65.

R-03 re-measured:

| Prompt | p/p (today) | q/p (naive swap) | q/q |
|---|---|---|---|
| what is still on my plate? | 0.932 | 0.882 | 0.932 |
| What's still on my plate this week? | 0.904 | 0.862 | 0.896 |
| O que tenho em aberto esta semana? | 0.875 | 0.860 | 0.847 |

The row the report flagged (`oq-hold-en-pos-01`) fails only on the naive swap. R-03 is not a detector bug: the detector catches the phrase in production.

**Decision: the detector stays in passage space. Threshold 0.88 and offset 0.05 do not move.** The retrieval vector becomes a query vector. `fetch_context` computes a second, passage-space vector of the prompt for the detector (about 32 ms on CPU, same call as today). The comment on the call names the calibration; `OPEN_QUERY_*` stays the single owner of the constants. A passage prefix on a user question is a calibrated feature choice here, not a claim about the text.

Held-out 3 (`open_query_holdout3.jsonl`) was written before any constant was chosen. Its first run gave EN 0.667 / PT 0.333 recall at zero FPR for the shipped detector. All four sets are now seen, so none is a clean verdict. The slow test pins the shipped numbers on held-out 1 to 3 as a regression guard. The deeper fix remains the 171 follow-up (a System One `asks_what_is_open` Noul); this floor does not build it.

### 3.2 Memory relevance floor

`relevance_floor: 0.35` (`episode: 0.30`) filters rows on raw cosine. Probe: 15 facts (EN + PT), 15 related questions, 12 unrelated questions.

| | passage-vs-passage (today) | query-vs-passage (new) |
|---|---|---|
| related, matching fact | min 0.763 · median 0.863 · max 0.927 | min 0.759 · median 0.820 · max 0.854 |
| unrelated, best fact | min 0.789 · median 0.819 · max 0.878 | min 0.726 · median 0.761 · max 0.802 |

Two results:

1. **The floor is inert in both modes.** The lowest unrelated score is 0.73, far above 0.35. `memory_relevance_floor_excludes_unrelated_facts` cannot pass on the floor today. The floor was set in phase 106 on MiniLM-era scales. The shim did not cause this.
2. **Query mode separates better.** The unrelated maximum falls from 0.878 (above the related median 0.863) to 0.802 (below the related median 0.820). Ranking by cosine improves.

**Decision: leave 0.35 / 0.30 unchanged in this floor.** S-01 moves no score across it (the closest new score is 0.73 against 0.35), so behavior is identical for the floor. An effective floor needs a labeled retrieval set (about 0.78 would drop half the unrelated probes but also the weaker cross-language matches, related min 0.759). A probe of 42 items is too small to set a production value. See open point 1.

Other constants on the same scale, all unchanged: `entity_anchor.match_constant 0.75` still ranks below real vector matches (related median 0.82); composite weights (similarity 0.6) keep their ratios.

### 3.3 Thresholds that stay exactly where they are

The symmetric-comparison rule keeps every non-retrieval threshold byte-identical: forget-by-embedding 0.88 / 0.80, `_MATCH_FLOOR` 0.55 / margin 0.05, loop dedup, correlation novelty, merchant merge, consolidator `MERGE_*`, dream novelty. A test per group pins which method the site calls.

## 4. U-01 — render tools for the companion

User decision (2026-10-16): the companion gets the ten unreachable `render_*` tools: `render_table`, `render_chart`, `render_metric`, `render_timeline`, `render_form`, `render_choice_group`, `render_consent`, `render_connect_account`, `render_review`, `render_connections`. No render tool is deleted.

- `CompanionAgent.tools` lists them. `ze_components.tools` registers at `ze_api.container` import, as for finance, so the plugin adds no import.
- All render tools are `ToolAccess.READ`, so Retry eligibility (165/180) and the write-confirmation gate (181) do not change. A test asserts every name is registered and READ.
- The companion prompt gets a short "Showing results" block: render when a table, chart, timeline, metric, or form beats prose; never render for chat; never narrate the tool call; render the setup/consent/connect tools only when the user is configuring something. Prose stays the default.
- Eval scenarios (`eval/scenarios/companion.yaml`), one per tool family, each with `expected_tools`: chart (`render_chart`), table (`render_table`), metric (`render_metric`), timeline (`render_timeline`), form (`render_form`), plus one for the setup trio and one for `render_connections`. Two negatives: a greeting and an emotional check-in must call no render tool.
- A routing check keeps companion answering normally: the existing companion scenarios plus the two negatives, and `eval/scenarios/routing.yaml` stays unchanged.

Running the scenarios live costs credits (the companion calls Sonnet). Nothing is run live without the user's OK.

## 5. Tests

Failing test first for each behavior change:

- `E5Embedder` has no `encode`; `encode_query` / `encode_passage` still prefix (existing tests, kept).
- Each query-side site calls `encode_query`; each stored / symmetric site calls `encode_passage` (fake embedder that raises on `encode` and records the method).
- `fetch_context` passes a query vector to `RetrievalRequest` and a passage vector to the open-query check.
- Every test fake that defined `encode` now defines `encode_query` and `encode_passage`.
- Companion `tools` contains the ten names; all are registered and READ.
- Slow test: shipped numbers on held-out 1 to 3.

## 6. Open points for the Maestro

1. **Relevance floor.** Leave at 0.35 / 0.30 (inert, unchanged), or open a follow-up that builds a labeled retrieval set and sets a real floor? Recommendation: follow-up. It is a product-visible recall trade and needs real data.
2. **Live scenario run.** Approve one live run of the new companion scenarios (about 9 turns on Sonnet) before review? Recommendation: yes, once, after the code is green.
3. **Cross-floor one-liners.** Seven files outside the §12 list lose `encode()`; confirm the overlap with CF-04 / CF-07 / CF-11 is acceptable. Recommendation: yes; each edit is one line.
