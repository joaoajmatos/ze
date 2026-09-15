# Phase 0 Research: Priority Turn Surfacing

## R1. Where the conversation consumer lives

**Decision**: A new `TurnSurfacing` service in `ze-priority` (`ze_priority/turn.py`).
The existing `surface_loops` graph node stays in `ze-core` and keeps its name
(verbatim constraint). It stops calling `LoopSurfacer.inline_candidates` and
instead reads a duck-typed `turn_surfacer` from `config["configurable"]`, the
same injection pattern Phase 110 used for `loop_surfacer`.

**Rationale**: Ranking, override merge, and cross-source relevance filtering are
`PriorityView` concerns. Putting them in `ze-worldstate` would make that package
depend on `ze-priority` (the wrong direction). Putting them in `ze-core` would
add a `ze-priority` import to the engine, which Constitution III and the Phase
110 plan both forbid. `ze-priority` already depends on the three source packages
and already owns `merge()`.

**Alternatives considered**:
- *Extend `LoopSurfacer.inline_candidates` to rank mixed sources.* Rejected —
  `ze-worldstate` would have to import `PriorityView` and the override store.
- *Have `surface_loops` call `PriorityView.rank()` directly.* Rejected —
  `ze-core` must not depend on `ze-priority`; the engine stays duck-typed.
- *Rename the graph node.* Rejected — the spec pins `surface_loops` as the
  existing path this phase replaces as the *source of which item is mentioned*.

## R2. Pins and decaying overrides: merge first, then filter

**Decision**: Unsolicited mentions and recap read the same snapshot the REST
view uses: `PriorityView.rank()` then `merge(ranking, overrides, now)`.
Relevance filtering runs *after* merge, preserving displayed order among the
items that survive. Do not `rank_subset` the relevant candidates — that would
re-score a trimmed list and drop pin positions defined against the full view.

**Rationale**: FR-002 requires user-directed pins from Phase 127. `rank()` itself
does not apply overrides; only `get_snapshot` / `merge()` does. Filtering after
merge keeps "goal pinned above loop" when both are relevant to the turn.

**Alternatives considered**:
- *Call `rank_subset` on already-relevant refs.* Rejected — merge is defined on
  the global order; a missing anchor would skip the pin.
- *Ignore overrides in conversation.* Rejected — FR-002 and SC-004.

## R3. Topical relevance per source, no new embedding

**Decision**: Same idea as Phase 110 entity-overlap, against whatever each
record already exposes. No per-turn embedding call.

| Source | Relevance test |
|---|---|
| loop | Turn entity ids overlap loops linked by graph `has_open_loop` (reuse `_loops_linked_to_entities`) |
| hypothesis | `Hypothesis.entities` ∩ turn entity ids (copied onto `PriorityItem.linked_entity_ids` at score time) |
| goal | Case-insensitive substring: any turn entity `canonical_name` / alias of length ≥ 3 appears in `title + " " + objective` (`PriorityItem.match_text`, filled at `score_goal`) |
| relationship | Case-insensitive match of `RelationshipSignal.name` against turn entity names/aliases |

Goals have no linked-entity column. Title+objective is the only topical handle
those records already carry. Relationships have no id other than a name-derived
UUID; name overlap is the equivalent match.

**Rationale**: Spec assumption: "Goals, hypotheses, and relationship nudges use
the same entity-overlap idea against whatever entities those records already
link — no new embedding call per turn."

**Alternatives considered**:
- *Skip goals/relationships in inline mentions because they lack graph edges.*
  Rejected — US1's independent test requires a stuck goal to win over a loop.
- *Embed goal text vs turn text.* Rejected by the spec's "no new embedding"
  assumption.

## R4. No loop-only fallback

**Decision**: If `TurnSurfacing` is missing, or `rank()` raises `ZePriorityError`
(every source failed), the turn completes with no mention. Do not fall back to
`LoopSurfacer.inline_candidates`. If the override store fails, degrade to the
unmerged `rank()` order rather than failing the turn or inventing a loop-only
list.

**Rationale**: Spec edge case and FR-009: a loop-only fallback would contradict a
higher-ranked relevant item the view could not rank. Partial source failure is
already handled inside `rank()`.

## R5. Inline mention bound

**Decision**: Unsolicited inline mentions are the top **3** relevant items after
merge, in displayed order. Today's `LoopSurfacer.inline_candidates` has no
numeric cap — it returns every overlapping *drifting* loop — but FR-011 forbids
dumping the snapshot. Three matches `_RELATIONSHIP_LIMIT_DEFAULT` and is enough
for the loops-only case (almost always 0–1 overlapping drifting loops) so that
path does not regress.

Explicit "what's open" and the resume-recap "Still open" slice are **not**
capped at 3: the user asked for, or the session gap is, the global list. The
working set is already tens of items (`PriorityView`'s own scale). Recap still
must not include non-`PriorityView` sources in that slice.

**Alternatives considered**:
- *Unbounded relevant set.* Rejected — FR-011.
- *Cap equal to "how many drifting loops overlapped."* Rejected as a hidden
  loop-preferring quota.

## R6. Resume recap: one ranked "Still open" slice

**Decision**: Replace `ResumeRecap.open_loop_lines` + `in_flight_goal_lines`
with one `open_item_lines` list built from the merged `PriorityView` snapshot
(global, no entity filter). Keep `in_flight_workflow_lines` as a separate
non-arbitration section. Drop `goal_store.list_active()` from this recap.

**Rationale**: FR-004 forbids source-by-source order. `PriorityView` already
defines what "unfinished business" means (open loops, stuck/near-gate goals,
live hypotheses, stale-relationship nudges). Healthy in-flight goals that are
not stuck are not an attention-arbitration source; listing them unranked next
to loops is the leftover this phase removes. Workflows are out of scope for
`PriorityView` and stay as their own recap lines.

**Alternatives considered**:
- *Keep all active goals as a second section.* Rejected — that recreates
  source-by-source assembly for the "what is open" slice.
- *Relevance-gate the recap like inline mentions.* Rejected — US2's independent
  test seeds a mixed ranking with no topical-overlap requirement; Phase 112
  already listed *all* active goals. The recap is a session-boundary "what's
  open," not a mid-turn mention.

## R7. Explicit "what's open" uses the resume-recap injection pattern

**Decision**: Detect a small set of global-list prompts (`what's open`, `what is
open`, `what's outstanding`, `what's on my plate`, and close variants) in
`TurnSurfacing.is_global_open_query(prompt)`. On those turns, `fetch_context`
sets `AgentContext.open_priorities_note` to the merged ranking rendered as one
ordered list. `BaseAgent._build_system_prompt` prepends it the same way it
prepends `resume_recap`. `surface_loops` then skips the unsolicited append so
the reply is not duplicated.

Do **not** add a `list_open_priorities` tool or switch `CompanionAgent` from
`complete()` to `agentic_loop`. Companion has `tools = []` and answers with
plain completion; the note is visible to every agent.

**Rationale**: FR-005 is "answered from `PriorityView` as one ordered list."
Companion is the likely route for "what's open right now." A tool the companion
cannot call would miss. Injecting only on an explicit ask is not a snapshot dump
into every turn (FR-011).

**Alternatives considered**:
- *Tool on `PriorityAgent` only.* Rejected — routing may send the question to
  companion.
- *Always append the global list from `surface_loops` after the model replies.*
  Rejected as a silent postscript; the model should *answer* from the list.

## R8. Preserve loop inline→push cooldown

**Decision**: When a mention's `source_kind == "loop"`, `TurnSurfacing` still
writes `push_log.log(f"worldstate_loop_inline:{loop_id}")`, the key
`LoopSurfacer.passes_push_bar` already checks. Push-budget numbers and the
greedy push check stay untouched (FR-007).

**Rationale**: Dropping the log would let a loop that was just mentioned inline
also win the shared push slot the same day.

## R9. Loop eligibility is PriorityView's, not drifting-only

**Decision**: Inline mentions may include any loop `PriorityView` already ranks
(`active` and `drifting`). Do not re-apply `LoopSurfacer`'s drifting-only
filter. Scoring already bonuses drifting loops, so a relevant drifting loop
still typically outranks a same-topic active one.

**Rationale**: This phase replaces *which* item is mentioned with `PriorityView`
order. Re-imposing drifting-only would prefer loops-as-drifting over a
higher-ranked stuck goal, which is the bug.

The loops-only case still looks like today when the only relevant item is a
drifting loop (R5).

## R10. Unconfirmed hypotheses stay hedged and off the push budget

**Decision**: Copy `Hypothesis.confirmed` into `PriorityItem.hedge`
(`hedge=True` when not confirmed). Mention text for hedged items uses
`format_hedged_mention` (already in `ze-worldstate.surfacing`). Do not exclude
unconfirmed hypotheses from the ranking (that would be a second ranking). Do
not change `AttentionArbitrationJob` or the shared budget (FR-007, FR-010).

**Rationale**: Phase 130 FR-010: unconfirmed inferences must not be presented as
settled identity and must not take shared attention-budget slots. Hedged inline
mention is the posture already specified there.

## R11. Hard-cut the mention payload shape

**Decision**: Replace the ad-hoc `drifting_loop_mentions` / component type
`drifting_loops` with `open_item_mentions` and component type `open_items`.
`ze-web` does not render `drifting_loops` today. Pre-v1 hard cuts apply; no shim.

**Rationale**: Constitution VIII. The component is already a dict the chat
surface mostly ignores; keeping a loop-only type would lie about contents.
