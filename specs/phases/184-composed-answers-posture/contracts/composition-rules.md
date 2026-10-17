# Contract: composition rules (`ze_priority/compose/`)

Normative for FR-007 to FR-010. Every rule is a pure function over records the composer fetched; I/O lives only in `WorldComposer`.

## Inputs (fetched in parallel; each failure is recorded, never raised)

| Source key | Call | Used by |
|---|---|---|
| `priority` | `PriorityView.rank()` → items + `sources_failed` (loop, goal, hypothesis, relationship) | slipping (relationship → person card), topic (hypotheses) |
| `loops` | `LoopStore.list(["suspected", "active", "drifting"])` | slipping, decisions, topic |
| `goals` | `GoalStore.list_progress()` (FR-016) | slipping (stuck), decisions (open gate), topic |
| `workflows` | `WorkflowStore.list_all()` + `list_executions(id, limit=1)` per matched workflow (topic only) | topic |
| `held_writes` | `HeldWriteStore.list(HeldWriteStatus.OPEN)` filtered to `expires_at > now` | decisions |

`sources_failed` = the source keys that raised, plus the `PriorityView` kinds it reports failed. All sources failed → headline `COULD NOT READ THE WORLD`, no components, summary "I could not read any of my sources just now."

## Constants

`WINDOW_DAYS = 7`, `LIST_CAP = 6` (per kind), `COMPOSITION_CAP = 12` cards, `PERSON_CAP = 2`, `TOPIC_FLOOR = ze_priority.tools._MATCH_FLOOR` (0.55; moved to a public name `MATCH_FLOOR` in `ze_priority/matching.py` and imported by both).

## `compose_slipping(now)`

- **slipped**: loops with `state == drifting` (card `slipped=True`, readout "slipped N d ago" from `drift_deadline` when set, line = `drift_rationale` when set); goals with `stuck_since` set (card `slipped=True`, `state="stuck"`, readout "no progress for N d" or "waiting on you for N d", progress done/total).
- **at risk**: loops with `state == active` and `now ≤ drift_deadline ≤ now + 7 d` (readout "due in N d", tone default).
- Order: slipped loops by `drift_deadline` ascending (oldest first), then stuck goals by `stuck_since` ascending, then at-risk by `drift_deadline`. Cap per kind 6, total 12.
- Components, in order: `Headline("N SLIPPING · M AT RISK")` (or `NOTHING SLIPPING`); `ClaimTimeline` of slipped + at-risk loops plus any active loop whose `drift_deadline` is within the window (omitted when empty); the cards; up to 2 person cards from `relationship` priority items (`subject="person"`, `kind="priority"`, `state="stale"`, line "Last contact N d ago").
- Summary (model-facing, ≤ 800 chars): counts, then one line per card: `slipped|at risk|stuck: <title> (<readout>)`, then `watching: <K> open concerns`, then `sources_failed` if any.

## `compose_decisions(now)`

- Held writes (open, not expired): card `subject="held_write"`, title = first item's `effect_phrase` + ": " + `summary` (+ " (+N more)"), line "From <source> '<owner name when known>'", readout "expires in N h", actions Approve (`approve_held_write`) / Deny (`deny_held_write`), `needs_user=True`.
- Goals with `gate_id` set: card `subject="goal"`, `state="awaiting_gate"`, line `gate_title`, readout "waiting N d", progress, actions Approve (`approve_gate`, `ref_id=gate_id`) / Open (`open`, `ref_id=goal id`), `needs_user=True`, `span=8`.
- Suspected loops: card `subject="loop"`, `kind` from the loop (`suspicion`), title as a question is the client's job; line "Seen in <source>", readout confidence, actions "Yes, track it" (`confirm_loop`) / Drop (`drop_loop`).
- Order: held writes (soonest expiry first), gates (oldest first), suspicions (highest confidence first). Cap per kind 6.
- Headline `N TO DECIDE` or `NOTHING TO DECIDE`. Summary: counts per kind and one line per card.

## `compose_topic(topic, now)`

- Embed `topic` once (`encode_passage`); for each candidate title compute cosine; keep `≥ MATCH_FLOOR`.
- Candidates: open loops (suspected/active/drifting), goals from `list_progress()` (title + objective, max of the two cosines), workflows (name + description), hypotheses from the priority ranking.
- Cards: loops (as in slipping/decisions, by cosine), goals (`span=8`, progress, next milestone line), workflows (`subject="workflow"`, `kind="priority"`, `state` from the last execution: `ok` / `failed` (`slipped=True`) / `never_run`, or `off` when disabled; readout last run "N h ago" and next run; line `failure_summary` when failed), hypotheses (`kind` from the hypothesis, dotted). Cap per kind 6.
- Headline `<TOPIC> · N SLIPPED · M WORKFLOWS` with `<TOPIC>` from `headline_text(topic)` truncated so the whole line fits 40 characters; nothing matched → `NOTHING ON <TOPIC>`.
- No embedder → empty composition, summary "I can't match topics right now."

## Preset path (`fetch_context`, FR-008)

1. Read `screen_context.compose`; valid values `slipping`, `decisions`, `topic` (requires non-empty `screen_context.topic`, ≤ 120 chars).
2. If the envelope is single-agent, not forced and not companion, replace it with the companion envelope built the way `_open_query_envelope` builds it (`routing_method="preset"`, full model).
3. Call the composer (2 s timeout; on timeout or error: no preset components, a warning, and normal routing continues with the reroute already applied).
4. Return `preset_components` and append to the companion system note: `[Composed answer for "<preset>" — the modules are already on screen. Write one or two sentences from this only, and offer one next step if it helps:\n<summary>]`.
5. The trace records `routing_method="preset"` (existing `RoutingTrace` field) so the trace panel can say why companion answered.

## Tools (FR-009)

`show_slipping()`, `show_decisions()`, `show_topic(topic: str)` — `ToolAccess.READ`, injected `world_composer`. Each appends the composition's components via `ze_components.context.append` (one call per component, in order) and returns `{"summary": str, "sources_failed": list[str]}`. A preset turn where the model also calls the tool for the same preset gets the components once: the tool returns the summary without appending when `preset_components` for that preset already exist in the turn (`ctx.extensions["preset"]`).
